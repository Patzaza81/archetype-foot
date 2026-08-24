"""
scraper_besoccer.py — Récupération GF/GA domicile/extérieur et historique
récent, depuis BeSoccer, via Playwright.

HISTORIQUE DE CE FICHIER, sans détour :
1. Version requests + pandas.read_html — rejetée par BeSoccer en HTTP 406,
   confirmé en conditions réelles (run GitHub Actions).
2. Ajout d'en-têtes navigateur complets (User-Agent/Accept/Accept-Language)
   — même échec 406, confirmé par un deuxième run réel.
3. Ajout des en-têtes Sec-Fetch-* + session avec cookies — MÊME ÉCHEC 406,
   confirmé par un troisième run réel, fraîchement relancé après ce correctif.
   Conclusion actée : ce n'est pas un problème d'en-têtes manquants, c'est une
   protection anti-bot qui les en-têtes seuls ne suffisent pas à contourner
   (empreinte de connexion, JavaScript requis, ou les deux).

Décision : Playwright pour BeSoccer uniquement. matchendirect reste en HTTP
simple (confirmé fonctionnel, aucune raison de changer ce qui marche).
"""

import re

import pandas as pd
from playwright.sync_api import sync_playwright

COLONNES_ATTENDUES = ["Pts", "MP", "W", "D", "L", "GK", "GA", "GD"]


def fetch_html(url, headless=True, timeout=30000):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=timeout)
        html = page.content()
        browser.close()
    return html


def _trouve_tables_classement(html):
    try:
        tables = pd.read_html(html)
    except ValueError as e:
        raise RuntimeError("Aucun tableau HTML trouvé sur la page — structure probablement changée.") from e

    candidates = [t for t in tables if all(c in t.columns for c in COLONNES_ATTENDUES)]
    if not candidates:
        raise RuntimeError(
            f"Aucun tableau avec les colonnes {COLONNES_ATTENDUES} trouvé. "
            f"Colonnes disponibles dans les tableaux de la page : "
            f"{[list(t.columns) for t in tables]}"
        )
    return candidates


def recupere_gf_ga_dom_ext(nom_equipe_slug):
    """
    nom_equipe_slug : identifiant BeSoccer dans l'URL, ex. 'paris-saint-germain-fc'.
    Retourne {'domicile': {'gf':.., 'ga':.., 'mp':..}, 'exterieur': {...}}
    """
    url = f"https://www.besoccer.com/team/table/{nom_equipe_slug}"
    html = fetch_html(url)
    tables = _trouve_tables_classement(html)

    if len(tables) < 3:
        raise RuntimeError(
            f"3 tableaux attendus (Total/Home/Away), {len(tables)} trouvé(s) pour {nom_equipe_slug}. "
            "Vérification manuelle nécessaire avant de faire confiance à ces chiffres."
        )

    table_home, table_away = tables[1], tables[2]

    def extrait_ligne_equipe(table, slug):
        for _, ligne in table.iterrows():
            texte_ligne = " ".join(str(v) for v in ligne.values)
            if slug.replace("-", " ") in texte_ligne.lower():
                return ligne
        return None

    ligne_home = extrait_ligne_equipe(table_home, nom_equipe_slug)
    ligne_away = extrait_ligne_equipe(table_away, nom_equipe_slug)

    if ligne_home is None or ligne_away is None:
        raise RuntimeError(
            f"Équipe '{nom_equipe_slug}' non trouvée dans le(s) tableau(x) Home/Away. "
            "Le slug ne correspond peut-être pas au texte affiché — vérification manuelle requise."
        )

    return {
        "domicile": {"gf": int(ligne_home["GK"]), "ga": int(ligne_home["GA"]), "mp": int(ligne_home["MP"])},
        "exterieur": {"gf": int(ligne_away["GK"]), "ga": int(ligne_away["GA"]), "mp": int(ligne_away["MP"])},
    }


def recupere_historique_matchs(nom_equipe_slug, max_matchs=10):
    """
    Retourne les `max_matchs` derniers matchs TERMINÉS (le plus récent
    d'abord), avec domicile/extérieur explicite et score.
    """
    from bs4 import BeautifulSoup

    url = f"https://www.besoccer.com/team/matches/{nom_equipe_slug}"
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    resultats = []
    for a in soup.select("a[href*='/match/']"):
        if len(resultats) >= max_matchs:
            break
        texte = a.get_text(" ", strip=True)
        m = re.search(r"(\d+)\s*-\s*(\d+)", texte)
        if not m:
            continue

        avant_score = texte[:m.start()].strip()
        apres_score = texte[m.end():].strip()
        if not avant_score or not apres_score:
            continue

        resultats.append({
            "domicile_brut": avant_score,
            "exterieur_brut": apres_score,
            "buts_domicile": int(m.group(1)),
            "buts_exterieur": int(m.group(2)),
            "url_match": a.get("href"),
        })

    if not resultats:
        raise RuntimeError(
            f"Aucun match terminé trouvé pour {nom_equipe_slug} via les liens /match/ — "
            "structure probablement différente de celle observée."
        )
    return resultats
