"""
test_scraping_betpawa_liste.py -- V7. Le paramètre d'URL deviné
(&day=Tomorrow) ne fonctionne pas (confirmé par requête statique,
31/08/2026) -- le filtre par jour doit passer par un appel réseau caché
déclenché en JavaScript. Ce script clique sur "Tomorrow" + "Apply" dans
le navigateur et ENREGISTRE toutes les requêtes réseau déclenchées, pour
identifier l'appel exact (URL + paramètres) à réutiliser ensuite
directement, sans navigateur.

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

        nb_requetes_avant_clic = len(requetes_capturees)

        resultat = "non tenté"
        texte_final = ""
        try:
            page.get_by_text("Tomorrow", exact=True).first.click(timeout=5000)
            page.wait_for_timeout(1000)
            page.get_by_text("Apply", exact=True).first.click(timeout=5000)
            page.wait_for_timeout(3000)
            texte_final = page.inner_text("body")
            resultat = "clic Tomorrow + Apply réussi"
        except Exception as e:
            resultat = f"échec : {e}"
            try:
                texte_final = page.inner_text("body")
            except Exception:
                pass

        url_finale = page.url
        navigateur.close()

    nouvelles_requetes = requetes_capturees[nb_requetes_avant_clic:]

    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        f.write(f"Résultat : {resultat}\n")
        f.write(f"URL finale (barre d'adresse) : {url_finale}\n\n")
        f.write(f"--- Requêtes réseau déclenchées par le clic ({len(nouvelles_requetes)}) ---\n")
        f.write("\n".join(nouvelles_requetes))
        f.write(f"\n\n--- Texte de la page après clic ---\n{texte_final}")

    print(f"Résultat : {resultat}")
    print(f"Nombre de requêtes capturées après clic : {len(nouvelles_requetes)}")
    for r in nouvelles_requetes:
        print(f"  {r}")

    print(f"\nRapport écrit dans {FICHIER_SORTIE} (committé par le workflow).")


if __name__ == "__main__":
    main()
