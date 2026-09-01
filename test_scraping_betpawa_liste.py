"""
test_scraping_betpawa_liste.py -- teste UNE question précise, avant de
construire quoi que ce soit dessus : une page de liste Betpawa
(events/group/...) contient-elle, après chargement JS, assez d'information
(équipes, heure, date) pour identifier plusieurs matchs à la fois --
contrairement à une page de match individuel (déjà exploitée par
scraper_betpawa.py), jamais utilisée à ce jour comme source de découverte.

Ce script ne fait partie d'AUCUN pipeline -- rien ne l'appelle
automatiquement. Il sert uniquement à répondre à cette question, sur le
modèle exact de test_scraping_betpawa.py (26/08), qui avait fait la même
chose pour les pages de match individuelles avant de construire
scraper_betpawa.py dessus.

IMPORTANT -- URL_TEST ci-dessous est un PLACEHOLDER. Il doit être remplacé
par une vraie URL de liste, copiée depuis Betpawa (naviguer jusqu'à la
liste des matchs d'un championnat, pas un match précis), avant que ce
script ait le moindre sens à exécuter.
"""
import sys

from playwright.sync_api import sync_playwright

# URL confirmée par recherche externe (31/08/2026) : page publique indexée
# "Bet on Upcoming Matches | betPawa Cameroon" -- jamais vérifiée en
# conditions réelles par ce projet à ce jour, d'où ce diagnostic avant
# d'aller plus loin.
URL_TEST = "https://www.betpawa.cm/events"

FICHIER_SORTIE = "diagnostic_liste_betpawa.txt"


def main():
    if URL_TEST.startswith("REMPLACER"):
        print("ERREUR : URL_TEST n'a pas été remplacée par une vraie URL "
              "de liste Betpawa. Rien à tester.", file=sys.stderr)
        sys.exit(1)

    print(f"Requête vers : {URL_TEST}")

    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        page = navigateur.new_page()
        page.goto(URL_TEST, timeout=30000, wait_until="domcontentloaded")

        # Pas de sélecteur précis à attendre (contrairement à
        # recupere_page() dans scraper_betpawa.py, qui attend "1X2" --
        # inconnu si une liste affiche ce texte). On attend simplement que
        # le réseau se calme, repli raisonnable pour une première
        # exploration.
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception as e:
            print(f"  networkidle jamais atteint ({e}) -- page probablement "
                  f"encore en chargement partiel, on continue quand même.")

        texte = page.inner_text("body")
        titre = page.title()
        navigateur.close()

    print(f"Titre de la page : {titre}")
    print(f"Taille du texte récupéré : {len(texte)} caractères")
    print()
    print("--- Extrait des 3000 premiers caractères ---")
    print(texte[:3000])
    print("--- Fin de l'extrait ---")

    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        f.write(f"URL testée : {URL_TEST}\n")
        f.write(f"Titre : {titre}\n")
        f.write(f"Taille : {len(texte)} caractères\n\n")
        f.write(texte)

    print(f"\nTexte complet écrit dans {FICHIER_SORTIE} (committé par le workflow).")


if __name__ == "__main__":
    main()
