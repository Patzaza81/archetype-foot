"""
test_scraping_betpawa_liste.py -- V13. Observation clé de Patrick
(31/08/2026) : sur son téléphone, il n'y a pas de barre de défilement --
il pose le doigt sur un match et pousse vers le haut (geste tactile).
Tous les tests précédents (V2, V11, V12) simulaient une molette de
souris d'ordinateur, jamais un vrai geste tactile -- ce qui peut
expliquer pourquoi rien ne se chargeait. Ce test émule un vrai
téléphone (viewport + tactile activé) et reproduit le geste exact
(appui, glissement vers le haut, relâchement) via les événements
tactiles bas niveau, au lieu d'une molette.

Ce script ne fait partie d'AUCUN pipeline -- rien ne l'appelle
automatiquement.
"""
import re

from playwright.sync_api import sync_playwright

URL_TEST = "https://www.betpawa.cm/events?categoryId=2&marketId=1X2"
FICHIER_SORTIE = "diagnostic_liste_betpawa.txt"


def compte_liens(page):
    return page.eval_on_selector_all("a[href*='/event/']", "els => els.length")


def geste_swipe_vers_le_haut(page, cdp, x, y_depart, y_arrivee, etapes_intermediaires=5):
    """Reproduit un vrai geste tactile : doigt posé, glissé progressivement
    vers le haut, puis relâché -- exactement le geste décrit par Patrick,
    au lieu d'une molette de souris."""
    cdp.send("Input.dispatchTouchEvent", {
        "type": "touchStart",
        "touchPoints": [{"x": x, "y": y_depart}],
    })
    for i in range(1, etapes_intermediaires + 1):
        y_courant = y_depart + (y_arrivee - y_depart) * i / etapes_intermediaires
        cdp.send("Input.dispatchTouchEvent", {
            "type": "touchMove",
            "touchPoints": [{"x": x, "y": y_courant}],
        })
        page.wait_for_timeout(50)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


def main():
    etapes = []

    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        # Émule un vrai téléphone (comme celui de Patrick) au lieu d'un
        # ordinateur -- viewport étroit, tactile activé.
        appareil = p.devices["iPhone 13"]
        contexte = navigateur.new_context(**appareil)
        page = contexte.new_page()
        cdp = contexte.new_cdp_session(page)

        page.goto(URL_TEST, timeout=30000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        etapes.append(f"Émulation téléphone active -- matchs au départ : {compte_liens(page)}")

        largeur = page.viewport_size["width"]
        hauteur = page.viewport_size["height"]

        for etape_scroll in range(15):
            nb_avant = compte_liens(page)
            # Doigt posé vers le bas de l'écran, glissé jusqu'en haut --
            # le geste exact décrit par Patrick.
            geste_swipe_vers_le_haut(page, cdp, largeur / 2, hauteur * 0.8, hauteur * 0.2)
            page.wait_for_timeout(1000)
            nb_apres = compte_liens(page)
            etapes.append(f"Swipe {etape_scroll + 1} : {nb_avant} -> {nb_apres} matchs")
            if nb_apres == nb_avant and etape_scroll > 3:
                etapes.append(f"Stabilisé après {etape_scroll + 1} swipes")
                break

        nb_final = compte_liens(page)
        etapes.append(f"Nombre final de matchs après swipes tactiles : {nb_final}")

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
