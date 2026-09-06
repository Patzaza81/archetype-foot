"""
scraper_semaine.py -- récupère le programme matchendirect des prochains
jours (par défaut J+2 à J+3 -- aujourd'hui et demain restent gérés par
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

CORRECTIF 03/09/2026 -- plage par défaut réduite de J+2/J+7 à J+2/J+3 :
Patrick a décidé de limiter toute la fenêtre (auto + panier manuel) à 4
jours (aujourd'hui à J+3). Les jours J+4 à J+7 scrapés jusqu'ici ne
servaient nulle part : ni à precalcul.py (qui ne lit que J+2/J+3 via
dates_j2_j3()), ni à l'onglet "semaine" de index.js (supprimé le même
jour -- il pointait de toute façon vers catalogue_unifie.json, un fichier
jamais généré par aucun script de ce dépôt).

CORRECTIF 06/09/2026 -- point #9 de l'audit (P0), déduplication par
match_id avant écriture : preuve directe sur données réelles (06/09) --
19 match_id présents sous DEUX dates différentes dans matchs_semaine.json
(J+2 ET J+3), tous des matchs entre 00h00 et 02h30 heure française. Ce
n'est PAS le bug de redirection silencieuse déjà connu sur "demain" dans
scraper.py (ce bug-là servirait une page identique à 100%, ici le
recouvrement mesuré n'est que de 6-7% des matchs de chaque jour) --
matchendirect.fr liste réellement ces matchs de coupure de minuit sur les
DEUX pages calendaires adjacentes. Une garde URL/date ne détecterait rien
ici puisque l'URL demandée correspond bien à la page servie. Conséquence
concrète trouvée en creusant : scraper_betpawa.cherche_url_matchendirect_auto()
concatène ce fichier sans déduplication -- ces matchs déclenchaient à tort
la branche "AMBIGU, aucune retenue" (2 candidats identiques par nom/URL)
et perdaient leur résolution automatique. `deduplique_par_match_id()`
ci-dessous supprime le doublon à la source, garde la première occurrence
rencontrée (= date la plus proche, la boucle scrape J+2 avant J+3), et
log chaque conflit réel sur stderr (jamais un écart silencieux).
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


def deduplique_par_match_id(matchs):
    """Déduplique une liste de matchs par match_id, garde la PREMIÈRE
    occurrence rencontrée dans l'ordre de la liste (= date la plus
    proche, puisque le scraping avance de J+2 vers J+3). Une entrée sans
    match_id est conservée telle quelle, sans dédup (aucun identifiant
    fiable pour la traiter). Un conflit réel (même match_id, dates
    différentes) est toujours signalé sur stderr -- jamais un écart
    silencieux. Un doublon exact (même match_id, même date, ex. deux
    passages sur la même page) est écarté sans log, cas normal et sans
    perte d'information."""
    vus = {}
    resultat = []
    for m in matchs:
        mid = m.get("match_id")
        if not mid:
            resultat.append(m)
            continue
        if mid in vus:
            premiere = vus[mid]
            if premiere.get("date") != m.get("date"):
                print(
                    f"  DOUBLON écarté : match_id={mid} "
                    f"({premiere.get('domicile')} - {premiere.get('exterieur')}) "
                    f"présent sous {premiere.get('date')} ET {m.get('date')} -- "
                    f"date retenue : {premiere.get('date')}",
                    file=sys.stderr,
                )
            continue
        vus[mid] = m
        resultat.append(m)
    return resultat


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jours-avant", type=int, default=2,
                         help="Premier jour à récupérer, en jours à partir d'aujourd'hui "
                              "(2 = après-demain, puisque aujourd'hui/demain sont déjà "
                              "couverts par scraper.py)")
    parser.add_argument("--jours-apres", type=int, default=3,
                         help="Dernier jour à récupérer (3 = fenêtre complète "
                              "limitée à J+3, voir CORRECTIF 03/09/2026)")
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
    # CORRECTIF FUSEAU HORAIRE 04/09/2026 -- voir run_pipeline.aujourdhui_france()
    from run_pipeline import aujourdhui_france
    aujourd_hui = aujourdhui_france()

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

    nb_avant_dedup = len(tous_les_matchs)
    tous_les_matchs = deduplique_par_match_id(tous_les_matchs)
    nb_doublons = nb_avant_dedup - len(tous_les_matchs)

    with open(args.sortie, "w", encoding="utf-8") as f:
        json.dump(tous_les_matchs, f, indent=2, ensure_ascii=False)
    print(f"{len(tous_les_matchs)} matchs au total (J+{args.jours_avant} à "
          f"J+{args.jours_apres}) -> {args.sortie}"
          + (f" ({nb_doublons} doublon(s) match_id écarté(s))" if nb_doublons else ""),
          file=sys.stderr)


if __name__ == "__main__":
    main()
