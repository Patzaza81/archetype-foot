"""
scraper.py — v2, réécrit après vérification directe du HTML de matchendirect.fr
(22/08/2026). Playwright abandonné : la liste des matchs du jour est rendue
côté serveur, un simple GET suffit.

Structure confirmée par récupération réelle de
https://www.matchendirect.fr/live-foot/ :
- Chaque match a un lien /live-score/{slug-equipe1}-{slug-equipe2}_{id}.html
- Le score, l'heure/statut et les noms d'équipes sont dans le texte du lien
- Les matchs sont groupés sous des en-têtes de compétition (### Pays : Compétition)

NON VÉRIFIÉ (Phase 2 du projet) : le contenu des onglets "FàF" (Face à Face)
et "Stats" sur la page de chaque match, nécessaires pour les GF/GA détaillés.
Ce script ne les récupère PAS encore — voir README.
"""

import argparse
import json
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.matchendirect.fr/live-foot/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ArchetypeFootBot/1.0; +https://github.com/)"
}

MATCH_LINK_RE = re.compile(r"^/live-score/([a-z0-9\-]+)_([a-z0-9]+)\.html$")


def fetch_html(url=BASE_URL, retries=3, delay=2):
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


def parse_matches(html, max_matchs=20):
    soup = BeautifulSoup(html, "html.parser")
    matchs = []
    seen_ids = set()

    for a in soup.select("a[href^='/live-score/']"):
        href = a.get("href", "")
        m = MATCH_LINK_RE.match(href)
        if not m:
            continue

        match_id = m.group(2)
        if match_id in seen_ids:
            continue

        texte = a.get_text(" ", strip=True)
        if not texte or len(texte) < 3:
            continue

        score_match = re.search(r"(.+?)\s+(\d+)\s*-\s*(\d+)\s+(.+)", texte)
        vs_match = re.search(r"(.+?)\s+v\s+(.+)", texte)

        if score_match:
            domicile, score_dom, score_ext, exterieur = score_match.groups()
            score = f"{score_dom}-{score_ext}"
        elif vs_match:
            domicile, exterieur = vs_match.groups()
            score = None
        else:
            continue

        competition = None
        header = a.find_previous(["h3"])
        if header:
            competition = header.get_text(" ", strip=True)

        seen_ids.add(match_id)
        matchs.append({
            "domicile": domicile.strip(),
            "exterieur": exterieur.strip(),
            "score": score,
            "competition": competition,
            "url_match": "https://www.matchendirect.fr" + href,
            "match_id": match_id,
        })

        if len(matchs) >= max_matchs:
            break

    return matchs


def scrape_programme_du_jour(max_matchs=20):
    html = fetch_html()
    return parse_matches(html, max_matchs=max_matchs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-matchs", type=int, default=20)
    parser.add_argument("--sortie", default="matches.json")
    args = parser.parse_args()

    matchs = scrape_programme_du_jour(max_matchs=args.max_matchs)

    with open(args.sortie, "w", encoding="utf-8") as f:
        json.dump(matchs, f, indent=2, ensure_ascii=False)

    print(f"{len(matchs)} matchs extraits -> {args.sortie}", file=sys.stderr)


if __name__ == "__main__":
    main()
