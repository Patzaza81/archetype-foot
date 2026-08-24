"""
scraper_details.py — Enrichissement matchendirect : classement dom/ext,
forme + H2H + cotes (page face-a-face), 20 derniers résultats (page
statistique). Tout en HTTP simple — aucune de ces pages n'a jamais renvoyé
d'erreur 406 ni de blocage, contrairement à BeSoccer (abandonné).

STATUT DE VÉRIFICATION : les URLs et la présence des données ont été
confirmées via un outil de récupération web (contenu extrait, pas le HTML
brut — même limite que partout ailleurs dans ce projet, voir scraper.py).
Ce script n'a jamais tourné contre le vrai HTML. Première vérification
réelle : le diagnostic GitHub Actions, comme pour scraper.py.
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


def recupere_details_match(url_match):
    """
    url_match : url /live-score/{slug}.html d'un match (page par défaut,
    SANS paramètre ?p=).
    Retourne {'lieu':..., 'meteo':..., 'arbitre':..., 'diffuseur':...,
              'url_statistique': ... ou None si lien absent}
    """
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

        table = next((t for t in tables if all(c in t.columns for c in COLONNES_CLASSEMENT)), None)
        if table is None:
            raise RuntimeError(
                f"Tableau de classement introuvable sur {url} ({cle}). "
                f"Colonnes vues : {[list(t.columns) for t in tables]}"
            )

        lignes = []
        for _, ligne in table.iterrows():
            nom_equipe = None
            for col in table.columns:
                val = ligne[col]
                if isinstance(val, str) and not val.strip().isdigit():
                    nom_equipe = val.strip()
                    break
            lignes.append({
                "equipe": nom_equipe,
                "pts": int(ligne["Pts"]), "j": int(ligne["J"]), "v": int(ligne["V"]),
                "n": int(ligne["N"]), "d": int(ligne["D"]), "bp": int(ligne["BP"]),
                "bc": int(ligne["BC"]), "diff": int(ligne["Diff"]),
            })
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


def recupere_20_derniers_resultats(url_statistique, nom_equipe_1, nom_equipe_2):
    html = fetch_html(url_statistique)
    soup = BeautifulSoup(html, "html.parser")

    resultat = {}
    for nom in (nom_equipe_1, nom_equipe_2):
        ancre_regex = rf"20 derniers résultats de {re.escape(nom)}"
        resultat[nom] = _extrait_matchs_scores(soup, ancre_regex, max_matchs=20)

    if not resultat[nom_equipe_1] and not resultat[nom_equipe_2]:
        raise RuntimeError(
            f"Aucun résultat trouvé sur {url_statistique} pour {nom_equipe_1} ni {nom_equipe_2} — "
            "structure probablement différente de celle observée."
        )
    return resultat


def recupere_h2h(url_match_face_a_face, max_confrontations=20):
    html = fetch_html(url_match_face_a_face)
    soup = BeautifulSoup(html, "html.parser")
    return _extrait_matchs_scores(soup, r"Confrontations entre les deux équipes", max_matchs=max_confrontations)


def recupere_cotes_marches(url_match_face_a_face):
    html = fetch_html(url_match_face_a_face)
    soup = BeautifulSoup(html, "html.parser")

    marches = {}
    for nom_marche, regex_titre, selections in [
        ("1x2", r"^Cotes 1N2$", ["1", "N", "2"]),
        ("double_chance", r"^Double chance$", ["1N", "12", "N2"]),
        ("btts", r"^Les 2 équipes marquent$", ["Oui", "Non"]),
    ]:
        titre = soup.find(string=re.compile(regex_titre))
        if titre is None:
            marches[nom_marche] = None
            continue
        nombres = []
        for element in titre.find_parent().find_all_next(limit=60):
            if element.name in ("h2", "h3"):
                break
            texte = element.get_text(strip=True) if hasattr(element, "get_text") else str(element).strip()
            if re.fullmatch(r"\d+[.,]\d{2}", texte):
                nombres.append(float(texte.replace(",", ".")))
        pas = len(selections)
        lignes = [nombres[i:i + pas] for i in range(0, len(nombres) - pas + 1, pas)]
        marches[nom_marche] = [dict(zip(selections, ligne)) for ligne in lignes if len(ligne) == pas]

    return marches
