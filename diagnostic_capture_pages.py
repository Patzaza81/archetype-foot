# -*- coding: utf-8 -*-
"""Capture de pages équipes matchendirect pour diagnostic (AJOUT 24/09/2026) — LECTURE SEULE.

Lancé par .github/workflows/diagnostic_pages.yml quand diagnostic/pages_a_capturer.txt change.
Pour chaque ligne « URL||compétition » : télécharge la page avec la MÊME fonction que le pipeline
(scraper_details.fetch_html), l'enregistre telle quelle dans diagnostic/pages/, et note ce que la lecture ACTUELLE
(scraper_details._extrait_historique_competition) en extrait, avec le texte qui a servi d'ancre et le titre de
compétition le plus proche au-dessus du tableau retenu. Sert à corriger la lecture sur de vraies pages, sans rien
changer au pipeline. N'écrit que dans diagnostic/.
"""
import json
import os
import re

from bs4 import BeautifulSoup

import scraper_details as sd

RACINE = os.path.dirname(os.path.abspath(__file__))
LISTE = os.path.join(RACINE, "diagnostic", "pages_a_capturer.txt")
DOSSIER = os.path.join(RACINE, "diagnostic", "pages")
SORTIE = os.path.join(RACINE, "diagnostic", "resultat_capture.json")


def _nom_equipe(url):
    return url.rsplit("/", 1)[-1].split("_")[0].replace("-", " ")


def _ancre_actuelle(soup, competition):
    """Reproduit la recherche d'ancre de _extrait_historique_competition (sans la modifier) pour savoir sur quoi elle tombe."""
    cible = sd._partie_competition(competition)
    for candidat in soup.find_all(string=True):
        texte = sd._normalise_texte(str(candidat))
        if ":" in texte and sd._competitions_correspondent(cible, sd._partie_competition(texte)):
            parent = candidat.find_parent()
            return {"texte": texte[:200], "balise_parent": parent.name if parent else None}
    return None


def main():
    os.makedirs(DOSSIER, exist_ok=True)
    resultats = []
    for ligne in open(LISTE, encoding="utf-8").read().splitlines():
        if "||" not in ligne:
            continue
        url, competition = [x.strip() for x in ligne.split("||", 1)]
        nom = _nom_equipe(url)
        entree = {"url": url, "competition": competition, "equipe": nom}
        try:
            html = sd.fetch_html(url)
        except Exception as e:  # noqa: BLE001 -- diagnostic : on note l'échec et on continue
            entree["erreur"] = str(e)
            resultats.append(entree)
            continue
        fichier = re.sub(r"[^a-z0-9]+", "_", nom.lower()) + ".html"
        with open(os.path.join(DOSSIER, fichier), "w", encoding="utf-8") as f:
            f.write(html)
        soup = BeautifulSoup(html, "html.parser")
        entree["fichier"] = "diagnostic/pages/" + fichier
        entree["ancre_actuelle"] = _ancre_actuelle(soup, competition)
        entree["extraction_actuelle"] = sd._extrait_historique_competition(soup, competition, nom)
        entree["titres_de_competition_sur_la_page"] = [" ".join(h.get_text(" ", strip=True).split())[:120] for h in soup.find_all(["h2", "h3", "h4"])][:40]
        resultats.append(entree)
    with open(SORTIE, "w", encoding="utf-8") as f:
        json.dump(resultats, f, ensure_ascii=False, indent=1)
    print(json.dumps(resultats, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
