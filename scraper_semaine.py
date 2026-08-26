"""
scraper_semaine.py -- récupère le programme matchendirect des prochains
jours (par défaut J+2 à J+7 -- aujourd'hui et demain restent gérés par
scraper.py) en utilisant un navigateur automatisé (Playwright), qui
contourne le problème confirmé en production sur `scraper.py` : une
requête HTTP classique sur /resultat-foot-{date}/ redirige silencieusement
vers la page du jour au lieu de la date demandée (25/08quater).

Réutilise `parse_matches()` de scraper.py TEL QUEL -- même logique de
lecture du HTML déjà éprouvée sur "aujourd'hui", seule la façon de
récupérer le HTML change (navigateur au lieu de requests). Ce fichier
n'importe et ne modifie jamais scraper.py -- risque zéro sur le chemin
"aujourd'hui" qui fonctionne déjà de façon fiable.

Sortie : matchs_semaine.json (liste plate, tous les jours confondus,
même format que matchs_du_jour.json/matchs_demain.json -- consommée par
scraper_betpawa.cherche_url_matchendirect_auto() en plus de ces deux
fichiers).

JAMAIS TESTÉ EN CONDITIONS RÉELLES au moment où ce fichier est écrit --
l'environnement d'édition n'a pas accès à matchendirect.fr. Le premier run
réel est le vrai test, comme pour scraper_betpawa.py en son temps.
"""
import argparse
import datetime
import json
import sys

from scraper import parse_matches, url_resultat_foot

FICHIER_SORTIE_DEFAUT = "matchs_semaine.json"


def scrape_jour_playwright(page, date_cible, max_matchs=200):
    """Récupère et parse le programme d'une date donnée via navigateur.
    Retourne une liste de matchs (peut être vide -- jour sans matchs
    n'est pas une erreur), lève une exception seulement si la page elle-
    même n'a pas pu être chargée du tout."""
    url = url_resultat_foot(date_cible)
    page.goto(url, timeout=30000, wait_until="domcontentloaded")
    html = page.content()
    return parse_matches(html, max_matchs=max_matchs, date_label=date_cible.isoformat())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jours-avant", type=int, default=2,
                         help="Premier jour à récupérer, en jours à partir d'aujourd'hui "
                              "(2 = après-demain, puisque aujourd'hui/demain sont déjà "
                              "couverts par scraper.py)")
    parser.add_argument("--jours-apres", type=int, default=7,
                         help="Dernier jour à récupérer (7 = une semaine)")
    parser.add_argument("--max-matchs", type=int, default=200)
    parser.add_argument("--sortie", default=FICHIER_SORTIE_DEFAUT)
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ÉCHEC : Playwright n'est pas installé -- voir l'étape "
              "d'installation dans pipeline.yml.", file=sys.stderr)
        # Non bloquant : écrit une liste vide plutôt que de faire planter
        # le pipeline pour une fonctionnalité annexe.
        with open(args.sortie, "w", encoding="utf-8") as f:
            json.dump([], f)
        sys.exit(0)

    tous_les_matchs = []
    aujourd_hui = datetime.date.today()

    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        page = navigateur.new_page()
        for delta in range(args.jours_avant, args.jours_apres + 1):
            date_cible = aujourd_hui + datetime.timedelta(days=delta)
            try:
                matchs_du_jour = scrape_jour_playwright(page, date_cible, max_matchs=args.max_matchs)
                print(f"  {date_cible.isoformat()} : {len(matchs_du_jour)} match(s)", file=sys.stderr)
                tous_les_matchs.extend(matchs_du_jour)
            except Exception as e:
                # Un jour qui échoue n'empêche pas de récupérer les autres --
                # même philosophie que "demain" dans scraper.py : échec
                # localisé, jamais un plantage global.
                print(f"  {date_cible.isoformat()} : ÉCHEC ({e})", file=sys.stderr)
        navigateur.close()

    with open(args.sortie, "w", encoding="utf-8") as f:
        json.dump(tous_les_matchs, f, indent=2, ensure_ascii=False)
    print(f"{len(tous_les_matchs)} matchs au total (J+{args.jours_avant} à "
          f"J+{args.jours_apres}) -> {args.sortie}", file=sys.stderr)


if __name__ == "__main__":
    main()
