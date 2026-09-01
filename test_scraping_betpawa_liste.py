"""
test_scraping_betpawa_liste.py -- V18. La V17 a confirmé de bout en bout
que la recherche par nom d'équipe fonctionne : cliquer sur la loupe,
taper un nom, cliquer sur la suggestion correspondante mène directement
à la page du match avec tous ses marchés. Ce test vérifie la fiabilité
de cette recette sur un échantillon de VRAIS matchs pris dans
precalcul.json (pas juste "Real Madrid", un cas facile) -- certains
noms d'équipes s'écrivent différemment entre matchendirect et Betpawa
(ex. "Talaea Gaish" vs "Talaea El Gaish"), donc ce test vérifie si une
correspondance simple (l'un des deux noms apparaît dans le texte d'une
suggestion) suffit, ou s'il faut une logique plus tolérante.

Ce script ne fait partie d'AUCUN pipeline -- rien ne l'appelle
automatiquement.
"""
import re

from playwright.sync_api import sync_playwright

URL_EVENTS = "https://www.betpawa.cm/events?categoryId=2&marketId=1X2"
FICHIER_SORTIE = "diagnostic_liste_betpawa.txt"

# Échantillon réel, pris dans precalcul.json le 31/08/2026 -- mélange de
# clubs obscurs et moyennement connus, pour un test honnête.
MATCHS_A_TESTER = [
    ("Bocholt", "Bonn"),
    ("Talaea Gaish", "ZED"),
    ("Sokół Ostróda", "Sokół Kleczew"),
    ("Brøndby", "Spartak"),
    ("West Bromwich", "Charlton"),
]


def cherche_et_clique(page, nom_domicile, nom_exterieur, etapes):
    """Reproduit la recette validée en V17 : ouvrir la recherche, taper
    le nom de l'équipe domicile, chercher parmi les suggestions celle
    qui contient aussi le nom de l'équipe extérieure, cliquer dessus."""
    try:
        page.locator("[aria-label*='earch' i]").first.click(timeout=5000)
        page.wait_for_timeout(800)

        champs = page.locator("input:not(#bookingCode)")
        champ = None
        for i in range(champs.count()):
            if champs.nth(i).is_visible():
                champ = champs.nth(i)
                break
        if champ is None:
            etapes.append(f"[{nom_domicile}] Aucun champ de recherche visible")
            return None

        champ.click(timeout=3000)
        page.keyboard.type(nom_domicile, delay=60)
        page.wait_for_timeout(1500)

        # Liste toutes les suggestions visibles, cherche celle qui
        # contient aussi le nom de l'équipe extérieure (comparaison
        # simple, insensible à la casse -- première approximation).
        suggestions = page.locator("div, span").filter(has_text=re.compile(re.escape(nom_domicile), re.IGNORECASE))
        textes_vus = []
        bonne_suggestion = None
        for i in range(min(suggestions.count(), 15)):
            try:
                texte = suggestions.nth(i).inner_text(timeout=1000)
            except Exception:
                continue
            if texte and texte not in textes_vus and len(texte) < 100:
                textes_vus.append(texte)
                if nom_exterieur.lower() in texte.lower():
                    bonne_suggestion = suggestions.nth(i)

        if bonne_suggestion is None:
            etapes.append(f"[{nom_domicile} - {nom_exterieur}] AUCUNE suggestion ne contient les deux noms. "
                          f"Suggestions vues : {textes_vus[:8]}")
            return None

        bonne_suggestion.click(timeout=5000)
        page.wait_for_timeout(2000)
        url = page.url
        etapes.append(f"[{nom_domicile} - {nom_exterieur}] TROUVÉ -> {url}")
        return url
    except Exception as e:
        etapes.append(f"[{nom_domicile} - {nom_exterieur}] ÉCHEC : {e}")
        return None


def main():
    etapes = []
    resultats = {}

    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        appareil = p.devices["iPhone 13"]
        contexte = navigateur.new_context(**appareil)
        page = contexte.new_page()

        for nom_domicile, nom_exterieur in MATCHS_A_TESTER:
            page.goto(URL_EVENTS, timeout=30000, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            url = cherche_et_clique(page, nom_domicile, nom_exterieur, etapes)
            resultats[f"{nom_domicile} - {nom_exterieur}"] = url

        navigateur.close()

    nb_trouves = sum(1 for v in resultats.values() if v)
    etapes.insert(0, f"Résultat global : {nb_trouves}/{len(MATCHS_A_TESTER)} matchs trouvés")

    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        f.write("--- Étapes ---\n" + "\n".join(etapes))

    print("\n".join(etapes))
    print(f"\nRapport écrit dans {FICHIER_SORTIE} (committé par le workflow).")


if __name__ == "__main__":
    main()
