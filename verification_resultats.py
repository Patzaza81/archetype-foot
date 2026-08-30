"""
verification_resultats.py -- (29/08/2026) ferme la boucle de vérification.

Va chercher automatiquement sur matchendirect le score final des matchs déjà
analysés (verdict_global GO ou NO_GO) dans historique_pronostics.json dont
le score n'est pas encore connu, pour les JOURS STRICTEMENT ANTÉRIEURS À
AUJOURD'HUI -- une journée entière écoulée veut dire que tous les matchs de
ce jour-là sont forcément terminés, pas besoin de suivre l'heure de coup
d'envoi match par match (plus simple et plus fiable que le seuil "+2h après
le coup d'envoi" envisagé au départ -- ce dernier suppose une heure de coup
d'envoi fiable par match, pas garantie dans les données existantes).

Réutilise le scraping déjà existant et déjà éprouvé en production :
- url_resultat_foot() / fetch_html() / parse_matches() (scraper.py) --
  exactement les pages "resultat-foot-DD-MM-YYYY" que Patrick collait à la
  main dans cette conversation pour la vérification manuelle.
- _memes_equipes() (scraper_details.py) -- même logique de rapprochement de
  noms d'équipes que le reste du pipeline, pas une nouvelle règle inventée
  ici.

Usage : python verification_resultats.py
Conçu pour tourner chaque jour via GitHub Actions (voir pipeline.yml),
indépendamment du panier -- ne touche qu'aux jours déjà écoulés.
"""
import datetime
import json
import sys

from scraper import parse_matches, url_resultat_foot, fetch_html
from scraper_details import _memes_equipes

FICHIER_HISTORIQUE = "historique_pronostics.json"
NB_JOURS_MAX_A_VERIFIER = 10  # au-delà, on abandonne (page trop ancienne /
                               # match jamais retrouvable ne doit pas faire
                               # boucler ce script indéfiniment)


def charge_historique():
    with open(FICHIER_HISTORIQUE, "r", encoding="utf-8") as f:
        return json.load(f)


def sauve_historique(historique):
    with open(FICHIER_HISTORIQUE, "w", encoding="utf-8") as f:
        json.dump(historique, f, ensure_ascii=False, indent=2)


def trouve_score(matchs_page, domicile, exterieur):
    """Ne renvoie un score que si le statut scrapé est bien "TER" (terminé).
    Un match reporté/suspendu, ou dont matchendirect n'affiche encore aucun
    score, ne doit jamais être écrit comme définitif dans l'historique --
    ça figerait un score faux ou vide pour toujours (le script ne repasse
    pas sur les jours déjà "traités une fois" au-delà de NB_JOURS_MAX)."""
    for m in matchs_page:
        if _memes_equipes(m["domicile"], domicile) and _memes_equipes(m["exterieur"], exterieur):
            if m.get("score") is not None and m.get("heure") == "TER":
                return m["score"]
            return None
    return None


def verifie_jour(jour):
    """Renvoie le nombre de scores nouvellement renseignés pour ce jour."""
    date_obj = datetime.date.fromisoformat(jour["date"])
    a_verifier = [m for m in jour.get("matchs", []) if m.get("verdict_global") and m.get("score") is None]
    if not a_verifier:
        return 0

    url = url_resultat_foot(date_obj)
    try:
        html, _ = fetch_html(url)
    except Exception as e:
        print(f"[verification] échec récupération {url} : {e}", file=sys.stderr)
        return 0

    # max_matchs=2000 : une page résultat contient plusieurs centaines de
    # matchs (toutes compétitions confondues, voir les pages collées dans
    # cette conversation) -- la valeur par défaut de parse_matches (20) en
    # perdrait la quasi-totalité silencieusement.
    matchs_page = parse_matches(html, max_matchs=2000, date_label=jour["date"])

    trouves = 0
    for m in a_verifier:
        score = trouve_score(matchs_page, m["domicile"], m["exterieur"])
        if score is not None:
            m["score"] = score
            m["score_verifie_le"] = datetime.datetime.utcnow().isoformat() + "Z"
            trouves += 1
    return trouves


def main():
    historique = charge_historique()
    aujourdhui = datetime.date.today()
    limite_ancienne = aujourdhui - datetime.timedelta(days=NB_JOURS_MAX_A_VERIFIER)

    total_trouves = 0
    total_restants = 0
    for jour in historique:
        date_obj = datetime.date.fromisoformat(jour["date"])
        if not (limite_ancienne <= date_obj < aujourdhui):
            continue  # jour d'aujourd'hui (pas fini) ou trop ancien (abandon)

        total_trouves += verifie_jour(jour)
        total_restants += sum(
            1 for m in jour.get("matchs", []) if m.get("verdict_global") and m.get("score") is None
        )

    sauve_historique(historique)
    print(f"[verification] {total_trouves} score(s) renseigné(s) -- "
          f"{total_restants} match(s) analysé(s) encore sans score après ce passage.")


if __name__ == "__main__":
    main()
