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

    resultat = {"lieu": None, "meteo": None, "arbitre": None, "diffuseur": None, "url_statistique": None}

    lien_stat = soup.select_one("a[href*='/statistique/']")
    if lien_stat:
        href = lien_stat.get("href", "")
        resultat["url_statistique"] = href if href.startswith("http") else "https://www.matchendirect.fr" + href

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

        matchs.append({
            "domicile_brut": noms[0],
            "exterieur_brut": noms[1],
            "buts_domicile": int(m.group(1)),
            "buts_exterieur": int(m.group(2)),
            "url_match": lien_match.get("href", ""),
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
        for element in titre.find_all_next(limit=200):
            texte = element.get_text(strip=True) if hasattr(element, "get_text") else str(element).strip()
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
