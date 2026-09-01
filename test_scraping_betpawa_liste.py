"""
test_scraping_betpawa_liste.py -- V12. La V11 a identifié le vrai
conteneur scrollable (classe "ScrollableWrapper_container", scrollHeight
4937 vs clientHeight 632) mais un saut direct (scrollTop = scrollHeight)
n'a rien chargé de plus -- probablement une liste virtualisée qui a
besoin de scrolls progressifs, comme un vrai doigt sur l'écran, pas un
saut brutal. Ce test scrolle ce conteneur précis par petits incréments.
Le clic sur "Demain" a aussi échoué une fois sur deux (intermittent) --
ajout d'une nouvelle tentative en cas d'échec.

Ce script ne fait partie d'AUCUN pipeline -- rien ne l'appelle
automatiquement.
"""
import re

from playwright.sync_api import sync_playwright

URL_TEST = "https://www.betpawa.cm/events?categoryId=2&marketId=1X2"
FICHIER_SORTIE = "diagnostic_liste_betpawa.txt"


def compte_liens(page):
    return page.eval_on_selector_all("a[href*='/event/']", "els => els.length")


def applique_filtre_demain(page, etapes, tentatives=3):
    for essai in range(1, tentatives + 1):
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
            etapes.append(f"Filtre Demain appliqué à l'essai {essai} -- matchs au départ : {compte_liens(page)}")
            return True
        except Exception as e:
            etapes.append(f"Essai {essai} échoué : {e}")
            page.wait_for_timeout(1000)
    return False


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

        applique_filtre_demain(page, etapes)

        # Scroll incrémental ciblé sur le vrai conteneur identifié en V11
        # (classe contenant "ScrollableWrapper"), par petits pas, avec
        # une pause à chaque étape pour laisser le temps au rendu
        # virtualisé de charger la suite.
        for etape_scroll in range(25):
            nb_avant = compte_liens(page)
            page.evaluate("""
                () => {
                    const els = document.querySelectorAll('*');
                    for (const el of els) {
                        if (el.className && String(el.className).includes('ScrollableWrapper')) {
                            el.scrollBy(0, 400);
                        }
                    }
                }
            """)
            page.wait_for_timeout(700)
            nb_apres = compte_liens(page)
            if nb_apres == nb_avant and etape_scroll > 3:
                etapes.append(f"Stabilisé après {etape_scroll} pas de scroll incrémental à {nb_apres} matchs")
                break

        nb_final = compte_liens(page)
        etapes.append(f"Nombre de matchs après scroll incrémental complet : {nb_final}")

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
