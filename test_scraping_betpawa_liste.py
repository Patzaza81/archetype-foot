"""
test_scraping_betpawa_liste.py -- V9. Patrick a confirmé par capture
d'écran (31/08/2026) que le filtre par jour n'est PAS dans "Markets"
(erreur des V7/V8) mais derrière une icône calendrier séparée, à droite
de "Markets" -- un troisième panneau indépendant, avec "Aujourd'hui /
Demain / [jours de la semaine]" et un bouton Apply. Ce test cible cette
icône par sa position (juste après le bouton "Markets"), sélectionne
"Demain", puis extrait tous les liens de matchs avec la méthode qui a
déjà fonctionné (V6).

Ce script ne fait partie d'AUCUN pipeline -- rien ne l'appelle
automatiquement.
"""
import re

from playwright.sync_api import sync_playwright

URL_TEST = "https://www.betpawa.cm/events?categoryId=2&marketId=1X2"
FICHIER_SORTIE = "diagnostic_liste_betpawa.txt"


def main():
    etapes = []

    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        page = navigateur.new_page()
        page.goto(URL_TEST, timeout=30000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        try:
            # L'icône calendrier est le bouton juste après "Markets" dans
            # la même barre de filtres -- pas de texte à cibler, on
            # prend l'élément frère suivant.
            bouton_markets = page.get_by_text("Markets", exact=True).first
            bouton_calendrier = bouton_markets.locator("xpath=../following-sibling::*[1]")
            bouton_calendrier.click(timeout=5000)
            page.wait_for_timeout(1500)
            etapes.append("clic sur l'icône après 'Markets' réussi")

            texte_panneau = page.inner_text("body")
            contient_demain = "Demain" in texte_panneau or "Tomorrow" in texte_panneau
            etapes.append(f"'Demain'/'Tomorrow' visible après ce clic : {contient_demain}")

            if "Demain" in texte_panneau:
                page.get_by_text("Demain", exact=True).first.click(timeout=5000)
            elif "Tomorrow" in texte_panneau:
                page.get_by_text("Tomorrow", exact=True).first.click(timeout=5000)
            page.wait_for_timeout(1000)
            etapes.append("clic sur 'Demain'/'Tomorrow' réussi")

            page.get_by_text(re.compile(r"^(Apply|Appliquer)$")).first.click(timeout=5000)
            page.wait_for_timeout(3000)
            etapes.append("clic sur Apply/Appliquer réussi")
        except Exception as e:
            etapes.append(f"échec à une étape : {e}")

        # Extraction des liens, qu'on ait réussi le filtre ou non --
        # utile dans les deux cas pour voir ce qui est réellement affiché.
        liens = page.eval_on_selector_all(
            "a[href*='/event/']",
            "els => els.map(e => ({href: e.href, texte: e.innerText}))"
        )

        navigateur.close()

    lignes_liens = [f"Nombre de liens /event/ trouvés après filtre : {len(liens)}\n"]
    for lien in liens:
        m = re.search(r"/event/(\d+)", lien["href"])
        id_event = m.group(1) if m else "?"
        texte_compact = " | ".join(l.strip() for l in lien["texte"].split("\n") if l.strip())
        lignes_liens.append(f"ID={id_event}  ::  {texte_compact}")

    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        f.write("--- Étapes ---\n" + "\n".join(etapes) + "\n\n")
        f.write("\n".join(lignes_liens))

    print("\n".join(etapes))
    print("\n".join(lignes_liens[:5]))
    print(f"\nRapport écrit dans {FICHIER_SORTIE} (committé par le workflow).")


if __name__ == "__main__":
    main()
