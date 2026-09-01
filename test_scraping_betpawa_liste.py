"""
test_scraping_betpawa_liste.py -- V2, teste deux questions précises avant
de construire quoi que ce soit :
1. Le défilement (scroll) charge-t-il plus de matchs que les ~20 visibles
   au premier chargement (confirmé lors du test V1, 31/08/2026) ?
2. Les jours suivants (J+1, J+2, J+3) apparaissent-ils dans cette même
   liste, ou faut-il une autre action (onglet, sélecteur de date) pour
   les voir ?

Ce script ne fait partie d'AUCUN pipeline -- rien ne l'appelle
automatiquement.
"""
import re
import sys

from playwright.sync_api import sync_playwright

URL_TEST = "https://www.betpawa.cm/events"
FICHIER_SORTIE = "diagnostic_liste_betpawa.txt"
NB_SCROLLS = 20
PAUSE_MS_ENTRE_SCROLLS = 1200


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

        taille_precedente = 0
        paliers = []
        for i in range(NB_SCROLLS):
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(PAUSE_MS_ENTRE_SCROLLS)
            texte_actuel = page.inner_text("body")
            taille_actuelle = len(texte_actuel)
            paliers.append(taille_actuelle)
            print(f"  scroll {i+1}/{NB_SCROLLS} -- taille du texte : {taille_actuelle} caractères")
            if taille_actuelle == taille_precedente:
                print("  taille stable sur ce scroll -- possible fin de liste atteinte")
            taille_precedente = taille_actuelle

        texte_final = page.inner_text("body")
        titre = page.title()
        navigateur.close()

    # Repère toutes les dates au format "JJ/MM" présentes dans le texte
    # (ex. dans "Tue 01/09"), pour savoir quels jours sont couverts.
    dates_trouvees = sorted(set(re.findall(r"\b(\d{2}/\d{2})\b", texte_final)))

    print(f"\nTitre de la page : {titre}")
    print(f"Taille finale du texte : {len(texte_final)} caractères")
    print(f"Dates distinctes repérées dans le texte : {dates_trouvees}")

    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        f.write(f"URL testée : {URL_TEST}\n")
        f.write(f"Titre : {titre}\n")
        f.write(f"Taille finale : {len(texte_final)} caractères\n")
        f.write(f"Paliers de taille au fil des {NB_SCROLLS} scrolls : {paliers}\n")
        f.write(f"Dates distinctes repérées (JJ/MM) : {dates_trouvees}\n\n")
        f.write("--- Texte complet après scroll ---\n")
        f.write(texte_final)

    print(f"\nTexte complet écrit dans {FICHIER_SORTIE} (committé par le workflow).")


if __name__ == "__main__":
    main()
