"""
test_scraping_betpawa_liste.py -- V8. La V7 a confirmé que "Tomorrow"
existe dans la page mais n'est pas visible (probablement caché dans le
panneau "Markets", qui doit être ouvert avant, comme "Leagues" devait
l'être pour voir les championnats). Ce test ouvre "Markets" d'abord,
PUIS clique sur "Tomorrow" + "Apply", en capturant les requêtes réseau
déclenchées.

Ce script ne fait partie d'AUCUN pipeline -- rien ne l'appelle
automatiquement.
"""
from playwright.sync_api import sync_playwright

URL_TEST = "https://www.betpawa.cm/events?categoryId=2&marketId=1X2"
FICHIER_SORTIE = "diagnostic_liste_betpawa.txt"


def main():
    requetes_capturees = []

    def sur_requete(request):
        if request.resource_type in ("xhr", "fetch"):
            requetes_capturees.append(f"{request.method} {request.url}")

    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        page = navigateur.new_page()
        page.on("request", sur_requete)

        page.goto(URL_TEST, timeout=30000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        etapes = []

        try:
            page.get_by_text("Markets", exact=True).first.click(timeout=5000)
            page.wait_for_timeout(1500)
            etapes.append("clic sur 'Markets' réussi")
        except Exception as e:
            etapes.append(f"échec clic 'Markets' : {e}")

        nb_avant_tomorrow = len(requetes_capturees)

        try:
            page.get_by_text("Tomorrow", exact=True).first.click(timeout=5000)
            page.wait_for_timeout(1000)
            etapes.append("clic sur 'Tomorrow' réussi")
        except Exception as e:
            etapes.append(f"échec clic 'Tomorrow' : {e}")

        try:
            page.get_by_text("Apply", exact=True).first.click(timeout=5000)
            page.wait_for_timeout(3000)
            etapes.append("clic sur 'Apply' réussi")
        except Exception as e:
            etapes.append(f"échec clic 'Apply' : {e}")

        try:
            texte_final = page.inner_text("body")
        except Exception:
            texte_final = "(impossible de lire le texte final)"

        url_finale = page.url
        navigateur.close()

    nouvelles_requetes = requetes_capturees[nb_avant_tomorrow:]

    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        f.write("--- Étapes ---\n" + "\n".join(etapes) + "\n\n")
        f.write(f"URL finale (barre d'adresse) : {url_finale}\n\n")
        f.write(f"--- Requêtes réseau déclenchées après ouverture Markets ({len(nouvelles_requetes)}) ---\n")
        f.write("\n".join(nouvelles_requetes))
        f.write(f"\n\n--- Texte de la page après clics ---\n{texte_final}")

    print("\n".join(etapes))
    print(f"Nombre de requêtes capturées : {len(nouvelles_requetes)}")
    for r in nouvelles_requetes:
        print(f"  {r}")

    print(f"\nRapport écrit dans {FICHIER_SORTIE} (committé par le workflow).")


if __name__ == "__main__":
    main()
