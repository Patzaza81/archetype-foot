"""
test_scraping_betpawa_liste.py -- V14. Nouvelle idée de Patrique
(31/08/2026), potentiellement la vraie solution : au lieu de lister tous
les matchs (plafonné à 20, scroll impossible malgré 5 méthodes testées),
utiliser le bouton recherche (loupe, visible en haut de l'écran sur son
téléphone) pour chercher directement un nom d'équipe -- celui qu'on a
déjà depuis matchendirect. Si ça marche, plus besoin de filtre jour ni
championnat : on cherche, on trouve, quel que soit le jour.

Ce test cherche le bouton recherche, clique dessus, tape un nom d'équipe
connu ("Real Madrid", exemple volontairement gros club pour être sûr
qu'il y a un match dans les jours à venir), et regarde ce qui apparaît.

Ce script ne fait partie d'AUCUN pipeline -- rien ne l'appelle
automatiquement.
"""
import re

from playwright.sync_api import sync_playwright

URL_TEST = "https://www.betpawa.cm/events?categoryId=2&marketId=1X2"
FICHIER_SORTIE = "diagnostic_liste_betpawa.txt"
NOM_TEST = "Real Madrid"


def main():
    etapes = []

    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        appareil = p.devices["iPhone 13"]
        contexte = navigateur.new_context(**appareil)
        page = contexte.new_page()

        page.goto(URL_TEST, timeout=30000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # Plusieurs façons possibles de désigner le bouton recherche --
        # on essaie plusieurs stratégies dans l'ordre jusqu'à ce qu'une
        # marche.
        strategies = [
            ("aria-label contenant 'search'", "[aria-label*='earch' i]"),
            ("bouton avec icône search générique", "button:has(svg[class*='earch' i])"),
            ("lien vers /search", "a[href*='search']"),
            ("icône loupe par classe", "[class*='earch' i]"),
        ]

        clic_reussi = False
        for nom_strategie, selecteur in strategies:
            try:
                element = page.locator(selecteur).first
                if element.count() > 0 and element.is_visible():
                    element.click(timeout=3000)
                    page.wait_for_timeout(1500)
                    etapes.append(f"Bouton recherche trouvé et cliqué via : {nom_strategie}")
                    clic_reussi = True
                    break
            except Exception as e:
                etapes.append(f"Stratégie '{nom_strategie}' échouée : {e}")

        if not clic_reussi:
            etapes.append("AUCUNE stratégie n'a trouvé le bouton recherche.")

        url_apres_clic = page.url
        etapes.append(f"URL après clic sur recherche : {url_apres_clic}")

        # Si un clic a réussi, on tente de taper le nom d'équipe dans le
        # premier champ de texte visible qui apparaît.
        if clic_reussi:
            try:
                champ = page.locator("input[type='text'], input[type='search'], input:not([type])").first
                champ.fill(NOM_TEST, timeout=5000)
                page.wait_for_timeout(2000)
                etapes.append(f"Nom '{NOM_TEST}' tapé dans le champ de recherche")
            except Exception as e:
                etapes.append(f"Échec de la saisie dans le champ : {e}")

        url_finale = page.url
        texte_final = page.inner_text("body")
        liens = page.eval_on_selector_all(
            "a[href*='/event/']",
            "els => els.map(e => ({href: e.href, texte: e.innerText}))"
        )

        navigateur.close()

    lignes_liens = [f"Nombre de liens /event/ trouvés après recherche : {len(liens)}\n"]
    for lien in liens:
        m = re.search(r"/event/(\d+)", lien["href"])
        id_event = m.group(1) if m else "?"
        texte_compact = " | ".join(l.strip() for l in lien["texte"].split("\n") if l.strip())
        lignes_liens.append(f"ID={id_event}  ::  {texte_compact}")

    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        f.write("--- Étapes ---\n" + "\n".join(etapes) + "\n\n")
        f.write(f"URL finale : {url_finale}\n\n")
        f.write("\n".join(lignes_liens))
        f.write(f"\n\n--- Texte complet de la page après recherche ---\n{texte_final}")

    print("\n".join(etapes))
    print(f"\nRapport écrit dans {FICHIER_SORTIE} (committé par le workflow).")


if __name__ == "__main__":
    main()
