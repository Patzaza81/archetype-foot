"""
test_scraping_betpawa_liste.py -- V15. Patrick a confirmé par capture
d'écran que la recherche par nom d'équipe fonctionne réellement (ex.
"Ipswich Town" -> 10 matchs). Deux corrections par rapport à la V14 :
1. Utiliser de vraies frappes clavier (page.keyboard.type) au lieu de
   .fill(), qui n'a visiblement pas déclenché la recherche de l'appli.
2. Cliquer explicitement sur le bouton "RECHERCHE" après la saisie --
   absent de la V14, cause probable de l'échec.

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

        try:
            page.locator("[aria-label*='earch' i]").first.click(timeout=5000)
            page.wait_for_timeout(1000)
            etapes.append("Bouton recherche cliqué")
        except Exception as e:
            etapes.append(f"Échec clic bouton recherche : {e}")

        try:
            # CORRECTIF V16 : la page contient plusieurs champs <input>
            # (dont "bookingCode", le code de pari, sans rapport avec la
            # recherche). .first prenait ce mauvais champ. On exclut
            # explicitement bookingCode et on prend le premier champ
            # visible restant.
            champs = page.locator("input:not(#bookingCode)")
            champ = None
            for i in range(champs.count()):
                if champs.nth(i).is_visible():
                    champ = champs.nth(i)
                    break
            if champ is None:
                raise Exception("Aucun champ de saisie visible autre que bookingCode")
            champ.click(timeout=3000)
            page.keyboard.type(NOM_TEST, delay=80)
            page.wait_for_timeout(1500)
            etapes.append(f"'{NOM_TEST}' tapé au clavier réel dans le bon champ")
        except Exception as e:
            etapes.append(f"Échec de la saisie clavier : {e}")

        try:
            page.get_by_text("RECHERCHE", exact=True).first.click(timeout=5000)
            page.wait_for_timeout(2500)
            etapes.append("Bouton RECHERCHE cliqué")
        except Exception as e:
            etapes.append(f"Échec clic RECHERCHE : {e}")

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
