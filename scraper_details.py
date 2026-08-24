"""
scraper_details.py — Enrichissement matchendirect : classement dom/ext,
forme + H2H + cotes (page face-a-face), 20 derniers résultats (page
statistique). Tout en HTTP simple — aucune de ces pages n'a jamais renvoyé
d'erreur 406 ni de blocage, contrairement à BeSoccer (abandonné).

STATUT DE VÉRIFICATION (24/08/2026) :
- details_match, H2H, 20 derniers résultats : testés OK sur run réel.
- classement : bug colonnes multi-niveaux corrigé une fois (aplatissement),
  un résidu subsistait (ligne d'en-tête "Saison Régulière" prise pour une
  ligne de données) — corrigé ici en filtrant les lignes non numériques.
- cotes : bug d'ancrage regex corrigé (titre trouvé), mais l'extraction
  mélangeait plusieurs marchés car les titres de section ne sont pas des
  balises h2/h3 réelles — la condition d'arrêt ne se déclenchait jamais.
  Corrigé ici en arrêtant au prochain titre de marché connu plutôt qu'à
  une balise de titre HTML qui n'existe pas sur cette page.
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

    # URLs des pages équipe : les deux premiers liens /equipe/ distincts dans
    # l'ordre du document correspondent à domicile puis extérieur (l'équipe
    # à domicile est toujours présentée en premier sur cette page).
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


# --------------------------------------------------------------------------
# Classement Général / Domicile / Extérieur
# CORRECTIF v2 (aplatissement colonnes) + CORRECTIF v3 (filtre lignes non
# numériques : la ligne d'en-tête de groupe "Saison Régulière" restait
# parfois comme première ligne de données après aplatissement).
# --------------------------------------------------------------------------

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
            # Filtre : ignore toute ligne résiduelle d'en-tête (valeur non
            # numérique dans une colonne censée être numérique).
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
                # Ligne non convertible malgré le filtre ci-dessus — on
                # l'ignore plutôt que de faire planter tout le classement.
                continue
        resultat[cle] = lignes
    return resultat


# --------------------------------------------------------------------------
# Page face-a-face : H2H — fonctionne, testé le 24/08.
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# Page statistique : 20 derniers résultats — corrigé et testé le 24/08.
# --------------------------------------------------------------------------

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

        # Compétition : dernier lien de la ligne, distinct du lien du match.
        # Nécessaire pour le filtre "même compétition" (TRANSITION.md 9.2) —
        # non appliqué ici, juste rendu disponible pour run_pipeline.py.
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
# Page face-a-face : cotes multi-bookmakers.
# CORRECTIF v3 : les titres de section ("Cotes 1N2", "Double chance", "Les
# 2 équipes marquent", "X.5 Plus / Moins"...) ne sont PAS des balises h2/h3
# — ce sont de simples nœuds de texte au même niveau que le reste. La
# condition d'arrêt sur h2/h3 ne se déclenchait donc jamais, et les nombres
# d'un marché débordaient sur le marché suivant. Correctif : s'arrêter au
# prochain titre de marché connu (les mêmes trois qu'on cherche, plus les
# variantes "Plus / Moins" et "Mi-temps") plutôt qu'à une balise HTML.
# --------------------------------------------------------------------------

TITRES_MARCHES_CONNUS = [
    "Cotes 1N2",
    "Double chance",
    "Les 2 équipes marquent",
    "Mi-temps - Résultat",
]
_REGEX_AUTRE_TITRE = re.compile(
    r"^(" + "|".join(re.escape(t) for t in TITRES_MARCHES_CONNUS) + r"|\d+(\.\d+)? Plus / Moins)$"
)


def recupere_cotes_marches(url_match_face_a_face):
    html = fetch_html(url_match_face_a_face)
    soup = BeautifulSoup(html, "html.parser")

    marches = {}
    for nom_marche, titre_attendu, selections in [
        ("1x2", "Cotes 1N2", ["1", "N", "2"]),
        ("double_chance", "Double chance", ["1N", "12", "N2"]),
        ("btts", "Les 2 équipes marquent", ["Oui", "Non"]),
    ]:
        titre = soup.find(string=lambda s: s and s.strip() == titre_attendu)
        if titre is None:
            marches[nom_marche] = None
            continue

        nombres = []
        # CORRECTIF : ne parcourir que les nœuds de texte (string=True),
        # jamais les balises. find_all_next() sans filtre renvoie à la fois
        # une balise <td>3.98</td> ET son contenu texte comme deux éléments
        # séparés dans l'itération — chaque cote était donc comptée deux
        # fois, ce qui décalait tout le regroupement par paquets de 3.
        for texte_brut in titre.find_all_next(string=True, limit=400):
            texte = texte_brut.strip()
            if not texte:
                continue
            # Arrêt dès qu'on retombe sur un titre de marché connu — le
            # nôtre pourrait réapparaître ailleurs sur la page (mini-widget
            # en haut de page pour "Mi-temps - Résultat" par exemple).
            if _REGEX_AUTRE_TITRE.match(texte):
                break
            if re.fullmatch(r"\d+[.,]\d{2}", texte):
                nombres.append(float(texte.replace(",", ".")))

        pas = len(selections)
        lignes = [nombres[i:i + pas] for i in range(0, len(nombres) - pas + 1, pas)]
        marches[nom_marche] = [dict(zip(selections, ligne)) for ligne in lignes if len(ligne) == pas]

    return marches


# --------------------------------------------------------------------------
# Classement universel via l'URL du match (25/08) — remplace le besoin d'une
# table de correspondance compétition -> slug de classement. N'importe quel
# match, dans n'importe quel championnat, a une URL /live-score/{slug}.html
# déjà scrapée par scraper.py ; l'onglet ?p=classement de CETTE URL donne le
# classement Saison Régulière de la compétition du match, sans construction
# manuelle de slug par ligue. Contrepartie assumée : classement combiné
# (pas de split domicile/extérieur séparé comme sur classement-foot/.../).
# Réutilise exactement la même logique de parsing (+ mêmes correctifs) que
# recupere_classement.
# --------------------------------------------------------------------------

def recupere_classement_du_match(url_match):
    """
    url_match : url /live-score/{slug}.html d'un match, SANS paramètre ?p=.
    Retourne une liste de {'equipe', 'pts', 'j', 'v', 'n', 'd', 'bp', 'bc', 'diff'}
    pour toute la compétition (classement Saison Régulière combiné).
    """
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
    """
    Recherche tolérante (insensible à la casse, sous-chaîne dans un sens ou
    l'autre) car les noms d'équipe peuvent différer légèrement entre la page
    programme du jour et la page classement (ex. 'Not. Forest' vs
    'Nottingham Forest'). Retourne None si rien de fiable trouvé — jamais de
    correspondance devinée au hasard.
    """
    nom_norm = nom_equipe.strip().lower()
    for ligne in classement:
        eq_norm = (ligne["equipe"] or "").strip().lower()
        if eq_norm == nom_norm or eq_norm in nom_norm or nom_norm in eq_norm:
            return ligne
    return None


# --------------------------------------------------------------------------
# Historique par compétition avec repli saison précédente (25/08) — remplace
# l'usage de recupere_classement_du_match pour gf/ga : au lieu d'une moyenne
# saison courante agrégée (pas de split domicile/extérieur, biaisée en début
# de saison par un faible nombre de matchs joués), on prend les VRAIS
# derniers matchs domicile et extérieur, en repliant sur la saison
# précédente UNIQUEMENT si la compétition est identique (garde-fou strict :
# une équipe promue/reléguée ne doit jamais hériter des chiffres de l'autre
# division). Les matchs amicaux sont exclus du calcul, jamais utilisés
# comme repli — contexte de jeu non comparable (effectifs remaniés, enjeu
# nul), même dilués avec un faible poids.
# --------------------------------------------------------------------------

def _normalise_texte(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _memes_equipes(nom1, nom2):
    """Comparaison tolérante — les noms peuvent différer légèrement entre
    pages (ex. 'Not. Forest' vs 'Nottingham Forest'). Best-effort assumé :
    en cas de doute, mieux vaut rater un rapprochement que d'en deviner un
    faux (voir _extrait_historique_competition, qui ignore une ligne plutôt
    que de l'attribuer à la mauvaise équipe)."""
    n1, n2 = _normalise_texte(nom1), _normalise_texte(nom2)
    return n1 == n2 or n1 in n2 or n2 in n1


def _saison_actuelle_et_precedente():
    """Convention saison européenne : la saison démarre en juillet.
    Retourne (saison_actuelle, saison_precedente) au format 'AAAA/AAAA'."""
    from datetime import date
    aujourd_hui = date.today()
    if aujourd_hui.month >= 7:
        debut = aujourd_hui.year
    else:
        debut = aujourd_hui.year - 1
    actuelle = f"{debut}/{debut + 1}"
    precedente = f"{debut - 1}/{debut}"
    return actuelle, precedente


def _extrait_historique_competition(soup, nom_competition, nom_equipe, max_matchs=10):
    """
    Retourne la liste des matchs JOUÉS (score présent) de `nom_equipe` dans
    la compétition `nom_competition`, sur la page déjà chargée (une saison).
    Retourne None si cette compétition n'apparaît pas du tout sur la page —
    c'est le garde-fou : absence de section = équipe pas dans cette
    compétition cette saison-là (promotion/relégation), on ne devine jamais
    une correspondance approximative de compétition.
    """
    cible = _normalise_texte(nom_competition)
    ancre = soup.find(string=lambda s: s and _normalise_texte(s) == cible)
    if ancre is None:
        return None
    table = ancre.find_parent().find_next("table")
    if table is None:
        return []

    matchs = []
    for tr in table.find_all("tr"):
        liens_avec_score = [a for a in tr.find_all("a") if re.search(r"\d+\s*-\s*\d+", a.get_text(" ", strip=True))]
        if not liens_avec_score:
            continue  # pas de score = match à venir, on l'ignore
        texte = liens_avec_score[0].get_text(" ", strip=True)
        m = re.match(r"^(.*?)\s+(\d+)\s*-\s*(\d+)\s+(.*)$", texte)
        if not m:
            continue
        nom_dom, buts_dom, buts_ext, nom_ext = m.group(1).strip(), int(m.group(2)), int(m.group(3)), m.group(4).strip()

        if _memes_equipes(nom_equipe, nom_dom):
            matchs.append({"domicile": True, "buts_marques": buts_dom, "buts_encaisses": buts_ext})
        elif _memes_equipes(nom_equipe, nom_ext):
            matchs.append({"domicile": False, "buts_marques": buts_ext, "buts_encaisses": buts_dom})
        # ni l'un ni l'autre -> ligne ignorée, jamais devinée

    return matchs


def recupere_gf_ga_avec_repli(url_equipe, nom_equipe, nom_competition, max_matchs=10):
    """
    Calcule gf/ga domicile et extérieur pour `nom_equipe` dans
    `nom_competition`, en utilisant en priorité la saison en cours, puis en
    complétant avec la saison précédente UNIQUEMENT si la compétition existe
    à l'identique sur cette page-là (garde-fou promotion/relégation, section
    9.2 de TRANSITION.md). Aucun match amical n'est utilisé.

    Retourne un dict :
      {'gf_domicile', 'ga_domicile', 'nb_domicile',
       'gf_exterieur', 'ga_exterieur', 'nb_exterieur'}
    ou {'raison_non_traite': str} si aucun match exploitable n'a été trouvé.
    """
    saison_actuelle, saison_precedente = _saison_actuelle_et_precedente()

    matchs_domicile, matchs_exterieur = [], []

    for saison in (saison_actuelle, saison_precedente):
        if len(matchs_domicile) >= max_matchs and len(matchs_exterieur) >= max_matchs:
            break
        try:
            url = url_equipe if saison == saison_actuelle else f"{url_equipe}?season={saison.replace('/', '%2F')}"
            html = fetch_html(url)
        except RuntimeError:
            continue  # saison précédente injoignable -> on s'arrête là, pas d'invention
        soup = BeautifulSoup(html, "html.parser")
        historique = _extrait_historique_competition(soup, nom_competition, nom_equipe, max_matchs)
        if historique is None:
            # Compétition absente sur cette page -> garde-fou : on n'utilise
            # PAS cette saison comme repli (promotion/relégation probable).
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
