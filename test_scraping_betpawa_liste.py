"""
test_scraping_betpawa_liste.py -- V3. La V2 (scroll via mouse.wheel) n'a
rien changé (confirmé 31/08/2026 : taille de texte strictement identique
sur 20 tentatives) -- la souris était probablement positionnée hors de la
zone scrollable. On teste autre chose ici : cliquer sur "Leagues", visible
en haut de la page, pour voir si ça révèle un filtre par pays/compétition
-- ce qui serait plus utile qu'un scroll générique, puisqu'on pourrait
cibler directement les compétitions qui nous intéressent.

Ce script ne fait partie d'AUCUN pipeline -- rien ne l'appelle
automatiquement.
"""
from playwright.sync_api import sync_playwright

URL_TEST = "https://www.betpawa.cm/events"
FICHIER_SORTIE = "diagnostic_liste_betpawa.txt"


def main():
    print(f"Requête vers : {URL_TEST}")

    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        page = navigateur.new_page()
        page.goto(URL_TEST, timeout=30000, wait_until="domcontentloaded")

        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception as e:
            print(f"  networkidle jamais atteint au chargement initial ({e})")

        texte_avant = page.inner_text("body")
        print(f"Taille avant clic : {len(texte_avant)} caractères")

        resultat_clic = "non tenté"
        texte_apres_clic = texte_avant
        try:
            page.get_by_text("Leagues", exact=True).first.click(timeout=5000)
            page.wait_for_timeout(2000)
            texte_apres_clic = page.inner_text("body")
            resultat_clic = f"clic réussi, taille après : {len(texte_apres_clic)} caractères"
        except Exception as e:
            resultat_clic = f"échec du clic sur 'Leagues' : {e}"

        print(f"Résultat du clic sur 'Leagues' : {resultat_clic}")

        # Deuxième tentative de scroll, cette fois en positionnant la
        # souris au centre de l'écran avant de faire défiler (la V2
        # scrollait avec la souris par défaut en haut à gauche, sur la
        # barre de navigation, pas sur la liste).
        largeur = page.viewport_size["width"]
        hauteur = page.viewport_size["height"]
        page.mouse.move(largeur / 2, hauteur / 2)
        taille_avant_scroll = len(page.inner_text("body"))
        for _ in range(10):
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(1000)
        texte_apres_scroll_centre = page.inner_text("body")
        taille_apres_scroll = len(texte_apres_scroll_centre)

        titre = page.title()
        navigateur.close()

    print(f"Taille avant scroll (souris centrée) : {taille_avant_scroll}")
    print(f"Taille après scroll (souris centrée) : {taille_apres_scroll}")

    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        f.write(f"URL testée : {URL_TEST}\n")
        f.write(f"Titre : {titre}\n\n")
        f.write(f"--- Résultat du clic sur 'Leagues' ---\n{resultat_clic}\n\n")
        f.write(f"--- Texte après clic sur 'Leagues' ---\n{texte_apres_clic}\n\n")
        f.write(f"--- Scroll avec souris centrée : {taille_avant_scroll} -> {taille_apres_scroll} caractères ---\n")
        f.write(texte_apres_scroll_centre)

    print(f"\nRésultats écrits dans {FICHIER_SORTIE} (committé par le workflow).")


if __name__ == "__main__":
    main()
