"""
diagnostic_navigation_reelle.py -- (06/09/2026) script de diagnostic
PONCTUEL. Teste l'idée de Patrick : au lieu de construire l'adresse
"?season=X" à la main (peu fiable -- voir diagnostic précédent), partir
de la page de la ligue (adresse stable, jamais devinée) et NAVIGUER
réellement -- clic sur l'équipe, puis clic sur la saison -- exactement
comme un humain le ferait, en utilisant un vrai navigateur (Playwright).

Compare deux façons d'arriver au même résultat, sur les MÊMES équipes :
A) "URL directe" : team.html?season=2025%2F2026 en une seule requête
   (méthode déjà testée, ~1 échec sur 2 environ)
B) "Navigation réelle" : ouvrir la page de la ligue, cliquer sur le nom
   de l'équipe pour arriver sur sa page, puis cliquer sur "2025/2026"
   dans le sélecteur de saisons

Si (B) réussit nettement plus souvent que (A), Patrick a raison : il
faut naviguer plutôt qu'inventer des adresses. Si les deux échouent au
même taux, le problème est ailleurs (aléa côté serveur, indépendant de
la méthode utilisée pour y arriver) -- ce script le dira clairement,
sans supposer la réponse à l'avance.

Ce script NE MODIFIE AUCUN FICHIER.

Usage : python diagnostic_navigation_reelle.py
"""
import sys

URL_LIGUE_1 = "https://www.matchendirect.fr/france/ligue-1-mcdonald-s_dm5ka0os1e3dxcp3vh05kmp33/"
EQUIPES_A_TESTER = ["Troyes", "RC Lens", "AJ Auxerre", "Strasbourg", "Lyon", "Lille"]
SAISON_CIBLE = "2025/2026"


def teste_url_directe(page, nom_equipe, url_equipe):
    """Méthode A -- une seule requête, adresse construite à la main."""
    url = f"{url_equipe}?season={SAISON_CIBLE.replace('/', '%2F')}"
    page.goto(url, timeout=20000, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    return page.locator("a[href*='/live-score/']").count()


def teste_navigation_reelle(page, nom_equipe):
    """Méthode B -- clic sur l'équipe depuis la page de la ligue, puis
    clic sur la saison cible, comme Patrick l'a fait à la main."""
    page.goto(URL_LIGUE_1, timeout=20000, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)

    lien_equipe = page.get_by_role("link", name=nom_equipe, exact=False).first
    if lien_equipe.count() == 0:
        print(f"[DIAG NAV] {nom_equipe!r} -- lien introuvable sur la page de la ligue.")
        return None
    lien_equipe.click(timeout=10000)
    page.wait_for_timeout(1500)

    url_equipe = page.url

    saison = page.get_by_text(SAISON_CIBLE, exact=True).first
    if saison.count() == 0:
        print(f"[DIAG NAV] {nom_equipe!r} -- sélecteur de saison introuvable sur sa page.")
        return None
    try:
        saison.click(timeout=5000, force=True)
    except Exception as e:
        print(f"[DIAG NAV] {nom_equipe!r} -- clic sur la saison échoué : {e}")
        return None
    page.wait_for_timeout(2000)

    return page.locator("a[href*='/live-score/']").count(), url_equipe


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ÉCHEC : Playwright n'est pas installé.")
        sys.exit(1)

    reussites_directe = 0
    reussites_navigation = 0
    total = 0

    with sync_playwright() as p:
        navigateur = p.chromium.launch()

        for nom_equipe in EQUIPES_A_TESTER:
            total += 1
            print(f"\n=== {nom_equipe} ===")

            # Contexte neuf à chaque fois -- pas de cookies partagés entre
            # equipes, pour ne pas fausser la comparaison.
            page_b = navigateur.new_page()
            resultat_b = teste_navigation_reelle(page_b, nom_equipe)
            url_equipe_trouvee = None
            if resultat_b:
                nb_liens_b, url_equipe_trouvee = resultat_b
                print(f"[DIAG NAV] {nom_equipe!r} -- Navigation réelle : {nb_liens_b} lien(s) /live-score/ "
                      f"trouvés après clic sur la saison (URL équipe : {url_equipe_trouvee}).")
                if nb_liens_b > 0:
                    reussites_navigation += 1
            page_b.close()

            if url_equipe_trouvee:
                page_a = navigateur.new_page()
                try:
                    nb_liens_a = teste_url_directe(page_a, nom_equipe, url_equipe_trouvee)
                    print(f"[DIAG NAV] {nom_equipe!r} -- URL directe : {nb_liens_a} lien(s) /live-score/ trouvés.")
                    if nb_liens_a > 0:
                        reussites_directe += 1
                except Exception as e:
                    print(f"[DIAG NAV] {nom_equipe!r} -- URL directe a échoué : {e}")
                page_a.close()

        navigateur.close()

    print(f"\n[DIAG NAV] RÉSUMÉ -- sur {total} équipe(s) testée(s) :")
    print(f"[DIAG NAV]   Navigation réelle (page ligue -> équipe -> saison) : {reussites_navigation}/{total} réussite(s)")
    print(f"[DIAG NAV]   URL directe (?season=X construit à la main) : {reussites_directe}/{total} réussite(s)")


if __name__ == "__main__":
    main()
