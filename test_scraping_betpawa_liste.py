"""
test_scraping_betpawa_liste.py -- V6. Objectif : extraire TOUS les liens
vers des matchs présents sur la page de liste (pas un par un), avec leur
ID Betpawa et l'heure/date affichée juste avant dans le texte, pour
étudier si l'ID suit une récurrence exploitable (ex. corrélé à l'heure
du match, à l'ordre d'ajout, etc.) -- question posée par Patrick le
31/08/2026 après plusieurs tests infructueux sur le filtrage par
championnat.

Ce script ne fait partie d'AUCUN pipeline -- rien ne l'appelle
automatiquement.
"""
import re

from playwright.sync_api import sync_playwright

URL_TEST = "https://www.betpawa.cm/events"
FICHIER_SORTIE = "diagnostic_liste_betpawa.txt"


def main():
    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        page = navigateur.new_page()
        page.goto(URL_TEST, timeout=30000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # Récupère tous les liens <a> dont le href contient "/event/",
        # avec le texte visible du bloc entier (contient normalement
        # l'heure, la date, les deux équipes).
        liens = page.eval_on_selector_all(
            "a[href*='/event/']",
            "els => els.map(e => ({href: e.href, texte: e.innerText}))"
        )

        titre = page.title()
        navigateur.close()

    lignes_rapport = [f"Nombre de liens /event/ trouvés : {len(liens)}\n"]
    for lien in liens:
        m = re.search(r"/event/(\d+)", lien["href"])
        id_event = m.group(1) if m else "?"
        texte_compact = " | ".join(l.strip() for l in lien["texte"].split("\n") if l.strip())
        lignes_rapport.append(f"ID={id_event}  ::  {texte_compact}")

    rapport = "\n".join(lignes_rapport)
    print(rapport[:3000])

    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        f.write(f"Titre : {titre}\n\n")
        f.write(rapport)

    print(f"\nRapport écrit dans {FICHIER_SORTIE} (committé par le workflow).")


if __name__ == "__main__":
    main()
