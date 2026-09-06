"""
diagnostic_selecteur_saison.py -- (06/09/2026) script de diagnostic PONCTUEL,
pas un script de production. Objectif unique : découvrir comment fonctionne
VRAIMENT le sélecteur "Saisons" sur la page d'une équipe matchendirect
(2026/2027, 2025/2026, 2024/2025, ...), pour pouvoir ensuite corriger
recupere_gf_ga_avec_repli() dans scraper_details.py.

Contexte (voir bilan du 06/09/2026) : `?season=2025%2F2026` ajouté à
l'URL de l'équipe est ignoré -- la page renvoyée est identique à la page
sans paramètre (confirmé par le tag <link rel="canonical"> de la page
elle-même, qui ne contient jamais ce paramètre). Le sélecteur "Saisons"
n'est donc probablement pas un lien classique -- ce script utilise un
vrai navigateur (Playwright, déjà une dépendance du projet pour
Betpawa) pour cliquer dessus comme le ferait un humain, et observe :
- l'URL de la page APRÈS le clic (page.url)
- toute requête réseau déclenchée par ce clic (interceptée via
  page.on("request"))
- si le contenu de la page a effectivement changé (nouveaux matchs
  affichés) ou si c'est un affichage cosmétique sans vrai rechargement

Usage : python diagnostic_selecteur_saison.py
Résultat : tout est imprimé dans les logs GitHub Actions -- pas de
fichier écrit, ce script ne modifie rien.
"""
import sys

URL_EQUIPE_TEST = "https://www.matchendirect.fr/equipe/troyes_3unkqo2g6ag99gd5ynz1j7vse.html"
SAISON_CIBLE_TEXTE = "2025/2026"


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ÉCHEC : Playwright n'est pas installé. Voir pipeline.yml "
              "(pip install playwright + playwright install --with-deps chromium).")
        sys.exit(1)

    requetes_vues = []

    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        page = navigateur.new_page()

        # On note TOUTE requête réseau déclenchée pendant la session, pour
        # repérer celle qui correspond au changement de saison (probablement
        # un appel XHR/fetch vers une URL différente de la page visible).
        page.on("request", lambda req: requetes_vues.append((req.method, req.url)))

        print(f"[DIAG SAISON] Ouverture de {URL_EQUIPE_TEST}")
        page.goto(URL_EQUIPE_TEST, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        url_avant = page.url
        # On capture le nombre de liens /live-score/ visibles AVANT clic,
        # pour comparer après (si le clic ne change rien, ce nombre restera
        # identique).
        nb_liens_avant = page.locator("a[href*='/live-score/']").count()
        print(f"[DIAG SAISON] URL avant clic : {url_avant}")
        print(f"[DIAG SAISON] Nombre de liens /live-score/ visibles avant clic : {nb_liens_avant}")

        nb_requetes_avant_clic = len(requetes_vues)

        # Le sélecteur de saisons peut être un <select>, une liste de <a>,
        # ou des <div>/<span> cliquables en JS pur -- on essaie plusieurs
        # façons de le trouver, dans l'ordre du plus probable au moins probable.
        clic_reussi = False
        essais = [
            ("texte exact cliquable", lambda: page.get_by_text(SAISON_CIBLE_TEXTE, exact=True).first),
            ("option de select", lambda: page.locator(f"option:has-text('{SAISON_CIBLE_TEXTE}')").first),
            ("lien contenant le texte", lambda: page.locator(f"a:has-text('{SAISON_CIBLE_TEXTE}')").first),
        ]
        for nom_essai, localisateur_fn in essais:
            try:
                element = localisateur_fn()
                if element.count() if hasattr(element, "count") else True:
                    print(f"[DIAG SAISON] Tentative de clic via : {nom_essai}")
                    element.scroll_into_view_if_needed(timeout=5000)
                    element.click(timeout=5000)
                    clic_reussi = True
                    print(f"[DIAG SAISON] Clic réussi via : {nom_essai}")
                    break
            except Exception as e:
                print(f"[DIAG SAISON] Échec de la tentative '{nom_essai}' : {e}")

        if not clic_reussi:
            print("[DIAG SAISON] AUCUNE méthode de clic n'a fonctionné -- "
                  "le sélecteur n'a été trouvé par aucune des 3 approches essayées.")
            navigateur.close()
            return

        page.wait_for_timeout(3000)

        url_apres = page.url
        nb_liens_apres = page.locator("a[href*='/live-score/']").count()
        nouvelles_requetes = requetes_vues[nb_requetes_avant_clic:]

        print(f"[DIAG SAISON] URL après clic : {url_apres}")
        print(f"[DIAG SAISON] URL a changé ? {url_avant != url_apres}")
        print(f"[DIAG SAISON] Nombre de liens /live-score/ visibles après clic : {nb_liens_apres}")
        print(f"[DIAG SAISON] Contenu visiblement changé (nb liens différent) ? {nb_liens_avant != nb_liens_apres}")
        print(f"[DIAG SAISON] {len(nouvelles_requetes)} nouvelle(s) requête(s) réseau déclenchée(s) par le clic :")
        for methode, url in nouvelles_requetes:
            print(f"[DIAG SAISON]   {methode} {url}")

        navigateur.close()


if __name__ == "__main__":
    main()
