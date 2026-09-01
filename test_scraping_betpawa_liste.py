"""
test_scraping_betpawa_liste.py -- V11. Le filtre "Demain" fonctionne
(confirmé : 20 matchs, tous datés du bon jour). Mais seulement 20 sur 82
annoncés -- il faut charger le reste. Ce test applique le même filtre
que la V10, PUIS essaie plusieurs méthodes de défilement l'une après
l'autre (scroll souris classique, touche "End", et scroll direct via
JavaScript sur le conteneur qui a vraiment une barre de défilement),
en comptant le nombre de matchs après chaque tentative pour voir
laquelle fonctionne.

Ce script ne fait partie d'AUCUN pipeline -- rien ne l'appelle
automatiquement.
"""
import re

from playwright.sync_api import sync_playwright

URL_TEST = "https://www.betpawa.cm/events?categoryId=2&marketId=1X2"
FICHIER_SORTIE = "diagnostic_liste_betpawa.txt"


def compte_liens(page):
    return len(page.eval_on_selector_all("a[href*='/event/']", "els => els.length"))


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

        # --- Réapplique le filtre Demain (recette V10, déjà validée) ---
        try:
            bouton_markets = page.get_by_text("Markets", exact=True).first
            bouton_calendrier = bouton_markets.locator("xpath=../following-sibling::*[1]")
            bouton_calendrier.click(timeout=5000)
            page.wait_for_timeout(1500)
            page.get_by_text("Demain", exact=True).first.click(timeout=5000)
            page.wait_for_timeout(1000)
            boutons_apply = page.get_by_text(re.compile(r"^(Apply|Appliquer)$"))
            for i in range(boutons_apply.count()):
                if boutons_apply.nth(i).is_visible():
                    boutons_apply.nth(i).click(timeout=5000)
                    break
            page.wait_for_timeout(3000)
            etapes.append(f"Filtre Demain appliqué -- matchs visibles au départ : {compte_liens(page)}")
        except Exception as e:
            etapes.append(f"échec application du filtre : {e}")

        # --- Méthode 1 : scroll souris classique, position centrée ---
        largeur = page.viewport_size["width"]
        hauteur = page.viewport_size["height"]
        page.mouse.move(largeur / 2, hauteur / 2)
        for _ in range(10):
            page.mouse.wheel(0, 2500)
            page.wait_for_timeout(600)
        etapes.append(f"Après scroll souris (10x) : {compte_liens(page)} matchs")

        # --- Méthode 2 : touche "End" ---
        for _ in range(5):
            page.keyboard.press("End")
            page.wait_for_timeout(600)
        etapes.append(f"Après touche End (5x) : {compte_liens(page)} matchs")

        # --- Méthode 3 : trouver le vrai conteneur scrollable et le scroller directement ---
        resultat_js = page.evaluate("""
            () => {
                const tous = document.querySelectorAll('*');
                let trouves = [];
                for (const el of tous) {
                    if (el.scrollHeight > el.clientHeight + 50 && el.clientHeight > 200) {
                        trouves.push({tag: el.tagName, classe: el.className, scrollH: el.scrollHeight, clientH: el.clientHeight});
                    }
                }
                return trouves.slice(0, 10);
            }
        """)
        etapes.append(f"Conteneurs scrollables détectés (top 10) : {resultat_js}")

        page.evaluate("""
            () => {
                const tous = document.querySelectorAll('*');
                for (const el of tous) {
                    if (el.scrollHeight > el.clientHeight + 50 && el.clientHeight > 200) {
                        el.scrollTop = el.scrollHeight;
                    }
                }
            }
        """)
        page.wait_for_timeout(2000)
        etapes.append(f"Après scroll JS direct sur conteneurs détectés : {compte_liens(page)} matchs")

        liens = page.eval_on_selector_all(
            "a[href*='/event/']",
            "els => els.map(e => ({href: e.href, texte: e.innerText}))"
        )

        navigateur.close()

    lignes_liens = [f"Nombre final de liens /event/ : {len(liens)}\n"]
    for lien in liens:
        m = re.search(r"/event/(\d+)", lien["href"])
        id_event = m.group(1) if m else "?"
        texte_compact = " | ".join(l.strip() for l in lien["texte"].split("\n") if l.strip())
        lignes_liens.append(f"ID={id_event}  ::  {texte_compact}")

    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        f.write("--- Étapes ---\n" + "\n".join(etapes) + "\n\n")
        f.write("\n".join(lignes_liens))

    print("\n".join(etapes))
    print(f"\nRapport écrit dans {FICHIER_SORTIE} (committé par le workflow).")


if __name__ == "__main__":
    main()
