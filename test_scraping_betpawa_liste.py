"""
test_scraping_betpawa_liste.py -- V5, REGROUPÉE. Teste plusieurs
hypothèses en un seul run, pour éviter les allers-retours répétés :

TEST A : sélectionner Premier League dans le filtre "Leagues" + APPLY --
         la liste se met-elle à jour avec plusieurs matchs/dates, et
         l'URL change-t-elle vers un format réutilisable ?
TEST B : après ce filtre, le scroll charge-t-il plus de matchs ?
TEST C : cliquer directement sur le nom d'une compétition affichée dans
         un match (ex. "Football / England / Premier League") -- mène-t-il
         à une page dédiée à cette compétition avec une URL propre ?
TEST D : recherche de tout élément de la page mentionnant "Tomorrow" /
         "Demain" / un sélecteur de date, pour voir s'il existe un moyen
         direct de changer de jour sans passer par les compétitions.

Ce script ne fait partie d'AUCUN pipeline -- rien ne l'appelle
automatiquement.
"""
import re

from playwright.sync_api import sync_playwright

URL_TEST = "https://www.betpawa.cm/events"
FICHIER_SORTIE = "diagnostic_liste_betpawa.txt"


def dates_dans(texte):
    return sorted(set(re.findall(r"\b(\d{2}/\d{2})\b", texte)))


def main():
    rapport = []

    def log(section, contenu):
        rapport.append(f"\n{'='*20} {section} {'='*20}\n{contenu}\n")
        print(f"--- {section} ---\n{contenu[:500]}\n")

    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        page = navigateur.new_page()
        page.goto(URL_TEST, timeout=30000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception as e:
            log("CHARGEMENT INITIAL", f"networkidle jamais atteint : {e}")

        texte_initial = page.inner_text("body")
        log("ÉTAT INITIAL", f"URL: {page.url}\nDates trouvées: {dates_dans(texte_initial)}\nTaille: {len(texte_initial)}")

        # --- TEST A : filtre Premier League + APPLY ---
        try:
            page.get_by_text("Leagues", exact=True).first.click(timeout=5000)
            page.wait_for_timeout(1500)
            page.get_by_text("Premier League", exact=True).first.click(timeout=5000)
            page.wait_for_timeout(1000)
            page.get_by_text("APPLY", exact=True).first.click(timeout=5000)
            page.wait_for_timeout(3000)
            texte_a = page.inner_text("body")
            log("TEST A -- Filtre Premier League + APPLY",
                f"URL après filtre: {page.url}\n"
                f"Dates trouvées: {dates_dans(texte_a)}\n"
                f"Taille: {len(texte_a)}\n\n"
                f"Texte complet:\n{texte_a}")
        except Exception as e:
            log("TEST A -- ÉCHEC", str(e))
            texte_a = texte_initial

        # --- TEST B : scroll après filtre ---
        try:
            largeur = page.viewport_size["width"]
            hauteur = page.viewport_size["height"]
            page.mouse.move(largeur / 2, hauteur / 2)
            for _ in range(8):
                page.mouse.wheel(0, 2000)
                page.wait_for_timeout(800)
            texte_b = page.inner_text("body")
            log("TEST B -- Scroll après filtre",
                f"Dates trouvées: {dates_dans(texte_b)}\n"
                f"Taille avant: {len(texte_a)} -> après scroll: {len(texte_b)}")
        except Exception as e:
            log("TEST B -- ÉCHEC", str(e))

        # --- TEST C : cliquer sur le nom d'une compétition dans un match ---
        try:
            page.goto(URL_TEST, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            lien_competition = page.get_by_text(re.compile(r"Football / .+ /.+")).first
            texte_lien = lien_competition.inner_text(timeout=5000)
            lien_competition.click(timeout=5000)
            page.wait_for_timeout(2500)
            texte_c = page.inner_text("body")
            log("TEST C -- Clic sur une compétition affichée dans un match",
                f"Texte du lien cliqué: {texte_lien}\n"
                f"URL après clic: {page.url}\n"
                f"Dates trouvées: {dates_dans(texte_c)}\n"
                f"Taille: {len(texte_c)}\n\n"
                f"Texte complet:\n{texte_c}")
        except Exception as e:
            log("TEST C -- ÉCHEC", str(e))

        # --- TEST D : recherche d'un sélecteur de date ---
        try:
            page.goto(URL_TEST, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            texte_d = page.inner_text("body")
            mentions = [mot for mot in ["Tomorrow", "Demain", "Today", "Aujourd'hui", "Calendar", "Date"] if mot in texte_d]
            log("TEST D -- Recherche d'un sélecteur de date",
                f"Mentions trouvées dans le texte: {mentions if mentions else 'AUCUNE'}")
        except Exception as e:
            log("TEST D -- ÉCHEC", str(e))

        navigateur.close()

    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        f.write("".join(rapport))

    print(f"\nRapport complet écrit dans {FICHIER_SORTIE} (committé par le workflow).")


if __name__ == "__main__":
    main()
