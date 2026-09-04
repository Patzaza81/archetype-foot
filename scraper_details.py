"""
scraper_details.py — Enrichissement matchendirect : classement dom/ext,
forme + H2H + cotes (page face-a-face), 20 derniers résultats (page
statistique). Tout en HTTP simple — aucune de ces pages n'a jamais renvoyé
d'erreur 406 ni de blocage, contrairement à BeSoccer (abandonné).
"""

import io
import re
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ArchetypeFootBot/1.0; +https://github.com/)"
}


def fetch_html(url, retries=3, delay=2):
    last_err = None
    for _ in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            last_err = e
            time.sleep(delay)
    raise RuntimeError(f"Échec de récupération de {url} après {retries} tentatives: {last_err}")


# --------------------------------------------------------------------------
# Détails de match + URL statistique réelle — fonctionne, testé le 24/08.
# --------------------------------------------------------------------------

def recupere_details_match(url_match):
    html = fetch_html(url_match)
    soup = BeautifulSoup(html, "html.parser")

    resultat = {"lieu": None, "meteo": None, "arbitre": None, "diffuseur": None,
                "url_statistique": None, "url_equipe_domicile": None, "url_equipe_exterieur": None}

    lien_stat = soup.select_one("a[href*='/statistique/']")
    if lien_stat:
        href = lien_stat.get("href", "")
        resultat["url_statistique"] = href if href.startswith("http") else "https://www.matchendirect.fr" + href

    urls_equipe_vues = []
    for a in soup.select("a[href*='/equipe/']"):
        href = a.get("href", "")
        href_abs = href if href.startswith("http") else "https://www.matchendirect.fr" + href
        if href_abs not in urls_equipe_vues:
            urls_equipe_vues.append(href_abs)
        if len(urls_equipe_vues) >= 2:
            break
    if len(urls_equipe_vues) >= 1:
        resultat["url_equipe_domicile"] = urls_equipe_vues[0]
    if len(urls_equipe_vues) >= 2:
        resultat["url_equipe_exterieur"] = urls_equipe_vues[1]

    texte_page = soup.get_text("\n", strip=True)
    for ligne in texte_page.split("\n"):
        if ligne.startswith("🏟"):
            resultat["lieu"] = ligne.lstrip("🏟").strip()
        elif ligne.startswith("🌡"):
            resultat["meteo"] = ligne.lstrip("🌡").strip()
        elif ligne.startswith("📣"):
            resultat["arbitre"] = ligne.lstrip("📣").strip()
        elif ligne.startswith("📺"):
            resultat["diffuseur"] = ligne.lstrip("📺").strip()

    return resultat


COLONNES_CLASSEMENT = ["Pts", "J", "V", "N", "D", "BP", "BC", "Diff"]


def recupere_classement(url_classement_base):
    variantes = {
        "general": url_classement_base,
        "domicile": url_classement_base + "?p=home",
        "exterieur": url_classement_base + "?p=away",
    }
    resultat = {}
    for cle, url in variantes.items():
        html = fetch_html(url)
        try:
            tables = pd.read_html(io.StringIO(html))
        except ValueError as e:
            raise RuntimeError(f"Aucun tableau trouvé sur {url} ({cle})") from e

        for t in tables:
            if isinstance(t.columns, pd.MultiIndex):
                t.columns = t.columns.get_level_values(-1)

        table = next((t for t in tables if all(c in t.columns for c in COLONNES_CLASSEMENT)), None)
        if table is None:
            raise RuntimeError(
                f"Tableau de classement introuvable sur {url} ({cle}). "
                f"Colonnes vues : {[list(t.columns) for t in tables]}"
            )

        lignes = []
        for _, ligne in table.iterrows():
            pts_brut = ligne["Pts"]
            if isinstance(pts_brut, str) and not pts_brut.strip().lstrip("-").isdigit():
                continue

            nom_equipe = None
            for col in table.columns:
                val = ligne[col]
                if isinstance(val, str) and not val.strip().lstrip("-").isdigit():
                    nom_equipe = val.strip()
                    break
            try:
                lignes.append({
                    "equipe": nom_equipe,
                    "pts": int(ligne["Pts"]), "j": int(ligne["J"]), "v": int(ligne["V"]),
                    "n": int(ligne["N"]), "d": int(ligne["D"]), "bp": int(ligne["BP"]),
                    "bc": int(ligne["BC"]), "diff": int(ligne["Diff"]),
                })
            except (ValueError, TypeError):
                continue
        resultat[cle] = lignes
    return resultat


def _extrait_matchs_scores(soup, ancre_regex, max_matchs=20):
    ancre = soup.find(string=re.compile(ancre_regex))
    if ancre is None:
        return []

    matchs = []
    conteneur = ancre.find_parent()
    if conteneur is None:
        return []

    for element in conteneur.find_all_next():
        if len(matchs) >= max_matchs:
            break
        if element.name in ("h2", "h3"):
            break
        if element.name == "a":
            href = element.get("href", "")
            if "/live-score/" in href or "/foot-score/" in href:
                texte = element.get_text(" ", strip=True)
                m = re.search(r"(\d+)\s*-\s*(\d+)", texte)
                if m:
                    avant = texte[:m.start()].strip()
                    apres = texte[m.end():].strip()
                    if avant and apres:
                        matchs.append({
                            "domicile_brut": avant,
                            "exterieur_brut": apres,
                            "buts_domicile": int(m.group(1)),
                            "buts_exterieur": int(m.group(2)),
                            "url_match": href,
                        })
    return matchs


def recupere_h2h(url_match_face_a_face, max_confrontations=20):
    html = fetch_html(url_match_face_a_face)
    soup = BeautifulSoup(html, "html.parser")
    return _extrait_matchs_scores(soup, r"Confrontations entre les deux équipes", max_matchs=max_confrontations)


def _parse_table_matchs(soup, ancre_regex, max_matchs=20):
    ancre = soup.find(string=re.compile(ancre_regex))
    if ancre is None:
        return []

    table = ancre.find_parent().find_next("table")
    if table is None:
        return []

    matchs = []
    for tr in table.find_all("tr"):
        if len(matchs) >= max_matchs:
            break

        lien_match = None
        for a in tr.find_all("a"):
            href = a.get("href", "")
            texte_lien = a.get_text(" ", strip=True)
            if ("/live-score/" in href or "/foot-score/" in href) and " - " in texte_lien \
                    and not re.search(r"\d+\s*-\s*\d+", texte_lien):
                lien_match = a
                break
        if lien_match is None:
            continue

        noms = [n.strip() for n in lien_match.get_text(" ", strip=True).split(" - ")]
        if len(noms) != 2:
            continue

        texte_ligne = tr.get_text(" ", strip=True)
        m = re.search(r"(\d+)\s*-\s*(\d+)", texte_ligne)
        if not m:
            continue

        liens_ligne = tr.find_all("a")
        lien_competition = liens_ligne[-1] if liens_ligne and liens_ligne[-1] is not lien_match else None
        competition = lien_competition.get_text(strip=True) if lien_competition else None

        matchs.append({
            "domicile_brut": noms[0],
            "exterieur_brut": noms[1],
            "buts_domicile": int(m.group(1)),
            "buts_exterieur": int(m.group(2)),
            "url_match": lien_match.get("href", ""),
            "competition": competition,
        })
    return matchs


def recupere_20_derniers_resultats(url_statistique, nom_equipe_1, nom_equipe_2):
    html = fetch_html(url_statistique)
    soup = BeautifulSoup(html, "html.parser")

    resultat = {}
    for nom in (nom_equipe_1, nom_equipe_2):
        ancre_regex = rf"20 derniers résultats de {re.escape(nom)}"
        resultat[nom] = _parse_table_matchs(soup, ancre_regex, max_matchs=20)

    if not resultat[nom_equipe_1] and not resultat[nom_equipe_2]:
        raise RuntimeError(
            f"Aucun résultat trouvé sur {url_statistique} pour {nom_equipe_1} ni {nom_equipe_2} — "
            "structure probablement différente de celle observée."
        )
    return resultat


# --------------------------------------------------------------------------
# Cotes — Bet365 uniquement (26/08). Voir docstring de la fonction pour le
# changement de méthode et la cause du bug précédent enfin confirmée.
# --------------------------------------------------------------------------

LIGNES_OVER_UNDER_CONNUES = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5]

TITRES_MARCHES_CONNUS = [
    "Cotes 1N2",
    "Double chance",
    "Les 2 équipes marquent",
    "Mi-temps - Résultat",
] + [f"{l} Plus / Moins" for l in LIGNES_OVER_UNDER_CONNUES]
_REGEX_AUTRE_TITRE = re.compile(
    r"^(" + "|".join(re.escape(t) for t in TITRES_MARCHES_CONNUS) + r")$"
)

BOOKMAKER_FIXE = "bet365"


def recupere_cotes_marches(url_match_face_a_face):
    """
    Retourne les cotes d'UN SEUL bookmaker fixe (Bet365), pour tous les
    marchés 1x2/double_chance/btts/over_under (0.5-7.5). dict simple
    (plus de tuple avec diagnostics -- inutile maintenant, la méthode
    n'a plus de mode de repli ambigu à surveiller).

    CHANGEMENT DE MÉTHODE (26/08) -- abandon du multi-bookmaker et de
    "minimum du panel" (approximation Betpawa), décision explicite.
    Cause du bug précédent confirmée en récupérant le vrai HTML : le nom
    de chaque bookmaker n'existe QUE dans l'attribut alt de son logo
    (<img alt="bet365 logo">), jamais comme texte visible. Le correctif
    25/08bis cherchait un "séparateur texte" entre bookmakers -- ça ne
    pouvait pas fonctionner ; ce qu'il détectait comme séparateur était
    probablement le caractère "-" (cote indisponible), cassant le
    comptage par paquets sur la quasi-totalité des lignes.

    Nouvelle méthode : ancrer directement sur l'image du bookmaker fixe
    (recherche par attribut alt), puis lire les valeurs qui suivent
    immédiatement jusqu'à la prochaine image ou la fin de section. Une
    valeur "-" devient None pour CETTE seule sélection, sans invalider
    le reste du marché. Bookmaker absent d'une section -> marché entier
    à None, jamais deviné.

    Choix de Bet365 : seul bookmaker observé présent sur toutes les
    lignes over/under, y compris les plus hautes (6.5, 7.5).
    """
    html = fetch_html(url_match_face_a_face)
    soup = BeautifulSoup(html, "html.parser")

    marches = {}
    definitions = [
        ("1x2", "Cotes 1N2", ["1", "N", "2"]),
        ("double_chance", "Double chance", ["1N", "12", "N2"]),
        ("btts", "Les 2 équipes marquent", ["Oui", "Non"]),
    ] + [
        (f"over_under_{l}", f"{l} Plus / Moins", ["plus", "moins"])
        for l in LIGNES_OVER_UNDER_CONNUES
    ]

    for nom_marche, titre_attendu, selections in definitions:
        # CORRECTIF (26/08bis) : un même titre de marché peut apparaître DEUX FOIS
        # sur la page -- une fois dans un widget d'aperçu en haut (sans Bet365),
        # une fois dans le tableau complet plus bas (avec Bet365). Confirmé sur
        # HTML réel (Valence-Real Betis, 25/08/2026) : "Mi-temps - Résultat"
        # apparaît une première fois dans l'aperçu (4 bookmakers, pas de Bet365)
        # puis une seconde fois dans le tableau complet (avec Bet365). soup.find()
        # ancrait sur la PREMIÈRE occurrence -- si un jour l'aperçu affiche un
        # marché qu'on exploite réellement (1N2, BTTS, une ligne O/U), la marche
        # find_all_next() sans limite dérive depuis l'aperçu à travers tout le
        # contenu intermédiaire (Détails du match, Pronostic...) jusqu'au
        # prochain titre reconnu -- pouvant renvoyer la cote Bet365 d'un AUTRE
        # marché, réelle mais associée à la mauvaise sélection, sans jamais lever
        # d'erreur. Cause probable du bug de cote invraisemblable (voir
        # TRANSITION.md, bug ouvert Gil Vicente-Casa Pia). Le tableau complet
        # étant structurellement le DERNIER endroit où un titre de marché
        # apparaît sur la page, on ancre désormais sur la dernière occurrence.
        titres = soup.find_all(string=lambda s: s and s.strip() == titre_attendu)
        titre = titres[-1] if titres else None
        if titre is None:
            marches[nom_marche] = None
            continue

        logo_bookmaker = None
        for element in titre.find_all_next():
            if isinstance(element, str):
                if _REGEX_AUTRE_TITRE.match(element.strip()):
                    break
                continue
            if element.name == "img":
                alt = (element.get("alt") or "").lower()
                if BOOKMAKER_FIXE in alt:
                    logo_bookmaker = element
                    break

        if logo_bookmaker is None:
            marches[nom_marche] = None
            continue

        valeurs = []
        for texte_brut in logo_bookmaker.find_all_next(string=True, limit=20):
            texte = texte_brut.strip()
            if not texte:
                continue
            if _REGEX_AUTRE_TITRE.match(texte):
                break
            if re.fullmatch(r"\d+[.,]\d{2}", texte):
                valeurs.append(float(texte.replace(",", ".")))
            elif texte == "-":
                valeurs.append(None)
            else:
                break
            if len(valeurs) >= len(selections):
                break

        marches[nom_marche] = (
            dict(zip(selections, valeurs)) if len(valeurs) == len(selections) else None
        )

    return marches


# --------------------------------------------------------------------------
# Classement universel via l'URL du match (25/08).
# --------------------------------------------------------------------------

def recupere_classement_du_match(url_match):
    url = url_match + "?p=classement"
    html = fetch_html(url)
    try:
        tables = pd.read_html(io.StringIO(html))
    except ValueError as e:
        raise RuntimeError(f"Aucun tableau de classement trouvé sur {url}") from e

    for t in tables:
        if isinstance(t.columns, pd.MultiIndex):
            t.columns = t.columns.get_level_values(-1)

    table = next((t for t in tables if all(c in t.columns for c in COLONNES_CLASSEMENT)), None)
    if table is None:
        raise RuntimeError(
            f"Tableau de classement introuvable sur {url}. "
            f"Colonnes vues : {[list(t.columns) for t in tables]}"
        )

    lignes = []
    for _, ligne in table.iterrows():
        pts_brut = ligne["Pts"]
        if isinstance(pts_brut, str) and not pts_brut.strip().lstrip("-").isdigit():
            continue
        nom_equipe = None
        for col in table.columns:
            val = ligne[col]
            if isinstance(val, str) and not val.strip().lstrip("-").isdigit():
                nom_equipe = val.strip()
                break
        try:
            lignes.append({
                "equipe": nom_equipe,
                "pts": int(ligne["Pts"]), "j": int(ligne["J"]), "v": int(ligne["V"]),
                "n": int(ligne["N"]), "d": int(ligne["D"]), "bp": int(ligne["BP"]),
                "bc": int(ligne["BC"]), "diff": int(ligne["Diff"]),
            })
        except (ValueError, TypeError):
            continue
    return lignes


def trouve_equipe_dans_classement(classement, nom_equipe):
    nom_norm = nom_equipe.strip().lower()
    for ligne in classement:
        eq_norm = (ligne["equipe"] or "").strip().lower()
        if eq_norm == nom_norm or eq_norm in nom_norm or nom_norm in eq_norm:
            return ligne
    return None


def _normalise_texte(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _memes_equipes(nom1, nom2):
    n1, n2 = _normalise_texte(nom1), _normalise_texte(nom2)
    return n1 == n2 or n1 in n2 or n2 in n1


def _saison_actuelle_et_precedente():
    from datetime import date
    aujourd_hui = date.today()
    if aujourd_hui.month >= 7:
        debut = aujourd_hui.year
    else:
        debut = aujourd_hui.year - 1
    actuelle = f"{debut}/{debut + 1}"
    precedente = f"{debut - 1}/{debut}"
    return actuelle, precedente


_MOTS_GENERIQUES_COMPETITION = {
    "league", "ligue", "liga", "lig", "liiga", "cup", "coupe", "division",
    "championship", "premiere", "premiere", "first", "1", "2",
}


def _mots_significatifs(partie_competition):
    """Retire les mots génériques ('league'/'ligue'/'liga'/'cup'/'coupe'...)
    qui varient d'une langue à l'autre sans rien dire de LA compétition
    précise -- ne garde que ce qui la distingue vraiment ('chinese',
    'super', 'premier', un nom propre...). Si tout est générique (nom
    d'une seule syllabe comme 'Superliga', déjà géré par l'inclusion de
    sous-chaîne), retombe sur les mots bruts plutôt que sur un ensemble
    vide, pour ne jamais perdre toute information de comparaison."""
    mots = [m for m in partie_competition.split() if m not in _MOTS_GENERIQUES_COMPETITION]
    return set(mots) if mots else set(partie_competition.split())


def _partie_competition(nom_competition):
    """Retire le préfixe pays ('Denmark :', 'Danemark :', etc.) -- il diffère
    presque toujours entre Betpawa (anglais) et matchendirect (français ou
    langue locale), et n'apporte rien à la comparaison : on cherche la même
    équipe sur SA PROPRE page matchendirect, le pays est donc déjà garanti
    correct par construction."""
    return _normalise_texte(nom_competition.split(":", 1)[-1])


def _competitions_correspondent(cible, candidat):
    if not cible or not candidat:
        return False
    if cible in candidat or candidat in cible:
        return True
    return bool(_mots_significatifs(cible) & _mots_significatifs(candidat))


def _extrait_historique_competition(soup, nom_competition, nom_equipe, max_matchs=10, diag_libelle=None):
    # CORRECTIF (26/08) : l'égalité stricte texte-complet ('Denmark :
    # Superliga' vs 'Danemark : Superligaen' sur la vraie page matchendirect,
    # confirmé en conditions réelles) échouait pour TOUT match venant de
    # Betpawa, pas seulement les cas rares -- le préfixe pays et
    # l'orthographe locale de la compétition ne correspondent jamais
    # exactement d'une source à l'autre. Remplacé par une comparaison sur le
    # nom de compétition seul (préfixe pays retiré des deux côtés).
    # CORRECTIF COMPLÉMENTAIRE (26/08, cas Qingdao) : la seule inclusion de
    # sous-chaîne ne suffisait pas non plus -- 'Chinese Super League' vs
    # 'Super Ligue' (vraie page matchendirect) diffèrent par la traduction
    # du mot 'league'/'ligue' lui-même, pas juste par l'ordre ou le pays.
    # Ajout d'une comparaison par mots significatifs communs (voir
    # _competitions_correspondent). Risque de faux positif jugé faible :
    # comme pour le premier correctif, on ne compare qu'un petit nombre de
    # rubriques (2 à 5) sur la page d'UNE équipe déjà identifiée avec
    # certitude, jamais entre équipes différentes.
    #
    # AJOUT DIAGNOSTIC 03/09/2026 (18.8) -- diag_libelle est un simple tag de
    # log (ex. "Newcastle | saison 2025/2026"), aucune incidence sur la
    # logique : uniquement des print() sur les chemins d'échec, pour savoir
    # OÙ ça casse (ancre introuvable ? table introuvable ? table trouvée
    # mais 0 ligne reconnue ?) sans toucher au comportement existant.
    cible = _partie_competition(nom_competition)
    ancre = None
    for candidat in soup.find_all(string=True):
        texte = _normalise_texte(str(candidat))
        if ":" not in texte:
            continue
        if _competitions_correspondent(cible, _partie_competition(texte)):
            ancre = candidat
            break
    if ancre is None:
        if diag_libelle:
            print(f"[DIAG 18.8] {diag_libelle} -- ancre INTROUVABLE pour "
                  f"compétition cible = {cible!r}. Aucun texte contenant ':' "
                  f"sur la page ne correspond.")
        return None
    table = ancre.find_parent().find_next("table")
    if table is None:
        if diag_libelle:
            print(f"[DIAG 18.8] {diag_libelle} -- ancre TROUVÉE ({ancre!r}) "
                  f"mais find_next('table') ne renvoie AUCUNE table après.")
        return []

    matchs = []
    for tr in table.find_all("tr"):
        liens_avec_score = [a for a in tr.find_all("a") if re.search(r"\d+\s*-\s*\d+", a.get_text(" ", strip=True))]
        if not liens_avec_score:
            continue
        texte = liens_avec_score[0].get_text(" ", strip=True)
        m = re.match(r"^(.*?)\s+(\d+)\s*-\s*(\d+)\s+(.*)$", texte)
        if not m:
            continue
        nom_dom, buts_dom, buts_ext, nom_ext = m.group(1).strip(), int(m.group(2)), int(m.group(3)), m.group(4).strip()

        if _memes_equipes(nom_equipe, nom_dom):
            matchs.append({"domicile": True, "buts_marques": buts_dom, "buts_encaisses": buts_ext})
        elif _memes_equipes(nom_equipe, nom_ext):
            matchs.append({"domicile": False, "buts_marques": buts_ext, "buts_encaisses": buts_dom})

    if diag_libelle and not matchs:
        nb_lignes = len(table.find_all("tr"))
        print(f"[DIAG 18.8] {diag_libelle} -- ancre ET table trouvées, mais "
              f"0 match reconnu sur {nb_lignes} ligne(s) <tr>. Le tableau "
              f"trouvé n'est probablement pas le bon (find_next a sauté "
              f"par-dessus la vraie table, ou format de ligne différent).")

    return matchs


def recupere_gf_ga_avec_repli(url_equipe, nom_equipe, nom_competition, max_matchs=10):
    saison_actuelle, saison_precedente = _saison_actuelle_et_precedente()

    matchs_domicile, matchs_exterieur = [], []

    for saison in (saison_actuelle, saison_precedente):
        if len(matchs_domicile) >= max_matchs and len(matchs_exterieur) >= max_matchs:
            break
        # AJOUT DIAGNOSTIC 03/09/2026 (18.8) -- tag lisible dans le log,
        # aucune incidence sur la logique (voir _extrait_historique_competition).
        diag_libelle = f"{nom_equipe} | {nom_competition!r} | saison {saison}"
        try:
            url = url_equipe if saison == saison_actuelle else f"{url_equipe}?season={saison.replace('/', '%2F')}"
            html = fetch_html(url)
        except RuntimeError as e:
            print(f"[DIAG 18.8] {diag_libelle} -- fetch_html a échoué sur "
                  f"{url!r} ({e}), saison ignorée.")
            continue
        soup = BeautifulSoup(html, "html.parser")
        historique = _extrait_historique_competition(
            soup, nom_competition, nom_equipe, max_matchs, diag_libelle=diag_libelle
        )
        if historique is None:
            continue
        for m in historique:
            if m["domicile"] and len(matchs_domicile) < max_matchs:
                matchs_domicile.append(m)
            elif not m["domicile"] and len(matchs_exterieur) < max_matchs:
                matchs_exterieur.append(m)

    if not matchs_domicile and not matchs_exterieur:
        return {"raison_non_traite": "aucun_match_joue_saison_actuelle_ou_precedente"}

    resultat = {"nb_domicile": len(matchs_domicile), "nb_exterieur": len(matchs_exterieur)}
    if matchs_domicile:
        resultat["gf_domicile"] = sum(m["buts_marques"] for m in matchs_domicile) / len(matchs_domicile)
        resultat["ga_domicile"] = sum(m["buts_encaisses"] for m in matchs_domicile) / len(matchs_domicile)
    if matchs_exterieur:
        resultat["gf_exterieur"] = sum(m["buts_marques"] for m in matchs_exterieur) / len(matchs_exterieur)
        resultat["ga_exterieur"] = sum(m["buts_encaisses"] for m in matchs_exterieur) / len(matchs_exterieur)
    return resultat
