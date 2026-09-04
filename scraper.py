"""
scraper.py — v3 (25/08bis) : ajout de l'heure de coup d'envoi, de la date, et
du programme de demain, en plus du programme du jour (v2, 22/08/2026).

VÉRIFIÉ EN CONDITIONS RÉELLES (25/08bis, via fetch direct hors de cet
environnement de production) :
- https://www.matchendirect.fr/live-foot/ (page "aujourd'hui") : chaque match
  a DEUX liens <a href="/live-score/{slug}_{id}.html"> distincts qui pointent
  vers la MÊME URL -- un badge horaire ("20:45") et le nom des équipes
  ("Reims v Annecy"). L'ancien code ne regardait que le deuxième et perdait
  l'heure silencieusement (jamais stockée nulle part). Corrigé ici en
  regroupant tous les <a> d'un même match_id avant de décider ce que chacun
  représente.
- Pour un match en direct ou terminé, le même badge affiche autre chose que
  "HH:MM" : minute écoulée ("83'"), "MT" (mi-temps), "TER" (terminé), "REP"
  (reporté). Ces valeurs sont conservées telles quelles dans "heure" --
  utile pour ne pas les confondre avec une heure de coup d'envoi.

NON VÉRIFIÉ EN CONDITIONS RÉELLES DANS L'ENVIRONNEMENT DE PRODUCTION (accès
réseau restreint à l'édition de ce fichier -- à confirmer au prochain run
réel du workflow, AVANT de faire confiance à la liste "demain") :
- L'URL "demain" affichée par le site est /resultat-foot-{DD-MM-YYYY}/ (lue
  dans la nav du site, confirmée deux fois avec deux dates différentes).
  MAIS un fetch direct de cette URL a échoué systématiquement avec une
  "boucle de redirection" lors des tests de vérification (outil de fetch
  utilisé pour ce diagnostic, pas `requests` -- le comportement réel de
  `requests.get` en production sur GitHub Actions peut différer, RIEN NE LE
  GARANTIT). scrape_programme("demain") est donc encapsulé pour échouer
  PROPREMENT (liste vide + avertissement explicite dans les logs) plutôt que
  de faire planter tout le pipeline si cette URL ne répond pas correctement
  en production. À VÉRIFIER AU PROCHAIN RUN : si les logs GitHub Actions
  montrent "ÉCHEC scraping demain", cette hypothèse d'URL est invalidée et
  il faut en chercher une autre (ou passer par un lien relatif trouvé
  dynamiquement dans le HTML de /live-foot/ plutôt que construit à la main).
"""
import argparse
import datetime
import json
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

BASE_URL_AUJOURDHUI = "https://www.matchendirect.fr/live-foot/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ArchetypeFootBot/1.0; +https://github.com/)"
}
MATCH_LINK_RE = re.compile(r"^/live-score/([a-z0-9\-]+)_([a-z0-9]+)\.html$")
RE_HEURE = re.compile(r"^\d{1,2}:\d{2}$")


def url_resultat_foot(date_obj):
    """URL "demain"/"hier" du site, construite depuis une date. Format
    DD-MM-YYYY confirmé via la nav réelle du site (liens "Demain"/"Hier")."""
    return f"https://www.matchendirect.fr/resultat-foot-{date_obj.strftime('%d-%m-%Y')}/"


def fetch_html(url, retries=3, delay=2):
    """Retourne (html, url_finale) -- url_finale est l'URL réellement servie
    après redirections éventuelles (requests les suit automatiquement sans
    lever d'erreur). Nécessaire pour détecter le cas "demain" ci-dessous."""
    last_err = None
    for _ in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            return resp.text, resp.url
        except requests.RequestException as e:
            last_err = e
            time.sleep(delay)
    raise RuntimeError(f"Échec de récupération de {url} après {retries} tentatives: {last_err}")


def parse_matches(html, max_matchs=20, date_label=None):
    """
    CORRECTIF (25/08bis) : les matchs ne sont plus traités <a> par <a> de
    façon indépendante. Un même match a plusieurs <a> avec le MÊME href
    (badge heure, noms d'équipes) -- on les regroupe par match_id d'abord,
    pour ne perdre ni l'heure ni les noms, quel que soit l'ordre
    d'apparition dans le HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    par_match = {}
    ordre = []

    for a in soup.select("a[href^='/live-score/']"):
        href_nu = a.get("href", "").split("?")[0]
        m = MATCH_LINK_RE.match(href_nu)
        if not m:
            continue
        match_id = m.group(2)
        texte = a.get_text(" ", strip=True)
        if not texte:
            continue

        if match_id not in par_match:
            par_match[match_id] = {
                "domicile": None, "exterieur": None, "score": None,
                "heure": None, "competition": None,
                "url_match": "https://www.matchendirect.fr" + href_nu,
                "match_id": match_id,
            }
            ordre.append(match_id)
        entree = par_match[match_id]

        if RE_HEURE.match(texte):
            entree["heure"] = texte
            continue

        score_match = re.search(r"(.+?)\s+(\d+)\s*-\s*(\d+)\s+(.+)", texte)
        vs_match = re.search(r"(.+?)\s+v\s+(.+)", texte)
        if score_match:
            domicile, score_dom, score_ext, exterieur = score_match.groups()
            entree["domicile"] = domicile.strip()
            entree["exterieur"] = exterieur.strip()
            entree["score"] = f"{score_dom}-{score_ext}"
        elif vs_match:
            domicile, exterieur = vs_match.groups()
            entree["domicile"] = domicile.strip()
            entree["exterieur"] = exterieur.strip()
        elif entree["heure"] is None:
            # Ni heure "HH:MM", ni score, ni "vs" -- badge de statut pour un
            # match en direct/fini ("83'", "MT", "TER", "REP"...). Conservé
            # tel quel dans "heure" si on n'a rien de mieux, pour ne pas
            # perdre l'info affichée sur le site.
            entree["heure"] = texte

        if entree["competition"] is None:
            header = a.find_previous(["h3"])
            if header:
                entree["competition"] = header.get_text(" ", strip=True)

    matchs = []
    for match_id in ordre:
        entree = par_match[match_id]
        if entree["domicile"] is None or entree["exterieur"] is None:
            continue
        if date_label:
            entree["date"] = date_label
        matchs.append(entree)
        if len(matchs) >= max_matchs:
            break
    return matchs


def scrape_programme(jour="aujourdhui", max_matchs=200):
    # CORRECTIF FUSEAU HORAIRE 04/09/2026 -- voir run_pipeline.aujourdhui_france()
    from run_pipeline import aujourdhui_france
    if jour == "aujourdhui":
        html, _ = fetch_html(BASE_URL_AUJOURDHUI)
        date_label = aujourdhui_france().isoformat()
    elif jour == "demain":
        date_cible = aujourdhui_france() + datetime.timedelta(days=1)
        url_demandee = url_resultat_foot(date_cible)
        html, url_finale = fetch_html(url_demandee)
        # CORRECTIF (confirmé en production, 25/08quater) : l'hypothèse
        # "non vérifiée" signalée plus haut s'est réalisée -- cette URL ne
        # sert pas vraiment le programme de demain en HTTP simple, elle
        # redirige silencieusement vers la page du jour. `requests` suit la
        # redirection sans lever d'erreur, donc sans ce contrôle explicite
        # de l'URL finale, "demain" recevait purement et simplement le
        # contenu d'"aujourd'hui" -- déjà observé en conditions réelles
        # (les deux onglets affichaient la même liste de 200 matchs).
        segment_attendu = f"resultat-foot-{date_cible.strftime('%d-%m-%Y')}"
        if segment_attendu not in url_finale:
            raise RuntimeError(
                f"L'URL demain ({url_demandee}) a redirigé vers {url_finale} "
                f"au lieu d'y rester -- cette page n'est probablement pas "
                f"accessible en HTTP simple (rendu côté client uniquement). "
                f"Traité comme un échec pour éviter de dupliquer les matchs "
                f"du jour sous l'étiquette 'demain'."
            )
        date_label = date_cible.isoformat()
    else:
        raise ValueError("jour doit être 'aujourdhui' ou 'demain'")
    return parse_matches(html, max_matchs=max_matchs, date_label=date_label)


# Conservé pour compatibilité (ancien nom de fonction utilisé ailleurs).
def scrape_programme_du_jour(max_matchs=20):
    return scrape_programme("aujourdhui", max_matchs=max_matchs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-matchs", type=int, default=200)
    parser.add_argument("--sortie-aujourdhui", "--sortie", dest="sortie_aujourdhui",
                         default="matchs_du_jour.json")
    parser.add_argument("--sortie-demain", default="matchs_demain.json")
    args = parser.parse_args()

    matchs_jour = scrape_programme("aujourdhui", max_matchs=args.max_matchs)
    with open(args.sortie_aujourdhui, "w", encoding="utf-8") as f:
        json.dump(matchs_jour, f, indent=2, ensure_ascii=False)
    print(f"{len(matchs_jour)} matchs (aujourd'hui) -> {args.sortie_aujourdhui}", file=sys.stderr)

    try:
        matchs_demain = scrape_programme("demain", max_matchs=args.max_matchs)
    except Exception as e:
        # Ne bloque JAMAIS la génération de la liste du jour -- voir la
        # note "NON VÉRIFIÉ" en tête de fichier sur l'URL "demain".
        print(f"ÉCHEC scraping demain (non bloquant) : {e}", file=sys.stderr)
        matchs_demain = []
    with open(args.sortie_demain, "w", encoding="utf-8") as f:
        json.dump(matchs_demain, f, indent=2, ensure_ascii=False)
    print(f"{len(matchs_demain)} matchs (demain) -> {args.sortie_demain}", file=sys.stderr)


if __name__ == "__main__":
    main()
