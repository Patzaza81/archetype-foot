"""
precalcul.py -- prépare automatiquement les pronostics de J+1, J+2 et J+3,
indépendamment de tout panier utilisateur.

Ne modifie ni calculs.py ni run_pipeline.py : réutilise construit_signaux()
tel quel (le moteur ne change pas), seule la source des matchs à traiter
change -- au lieu de panier.json (sélection manuelle), on prend directement
matchs_demain.json (J+1) + matchs_semaine.json filtré sur les deux dates
suivantes (J+2, J+3).

AJOUT 01/09/2026 : avant construit_signaux(), chaque match de la fenêtre
passe par resolution_betpawa_precalcul.resout_cotes_betpawa(), qui tente
de trouver sa correspondance Betpawa et d'en récupérer les cotes réelles.
Voir resolution_betpawa_precalcul.py pour le détail.

AJOUT 02/09/2026 : archive_precalcul() enregistre dans
historique_pronostics.json (même fichier que run_pipeline.py, format
compatible, réutilisé sans modification de verification_resultats.py) une
version allégée des matchs READY -- SEULEMENT ceux dont la date est J+1
(demain), jamais J+2/J+3, pour ne jamais archiver le même match plusieurs
fois à mesure qu'il avance dans la fenêtre au fil des nuits. Sans ça, le
pré-calcul nocturne calculait des centaines de pronostics par nuit qui ne
rentraient jamais dans le circuit de vérification (verification_resultats.py
ne lit QUE historique_pronostics.json) -- donc jamais utilisables pour
mesurer un ROI réel ni construire l'échantillon de ~1000 matchs vérifiés visé.
Version volontairement allégée (pas les distributions de probabilité
complètes) pour ne pas faire exploser la taille du fichier au fil du temps.

Sortie : precalcul.json (inchangé dans sa fonction), avec en plus :
  - nb_archives_historique : nombre de matchs J+1 READY archivés ce run
Et historique_pronostics.json, grossi d'une entrée par date de match J+1
présente ce soir (normalement une seule, celle de demain).

JAMAIS EXÉCUTÉ EN CONDITIONS RÉELLES au moment où ce fichier est écrit --
voir procédure de vérification donnée à Patrick en dehors de ce fichier.
"""
import datetime
import json
import sys

import run_pipeline
from run_pipeline import construit_signaux, charge_json_ou_vide
from cache_equipes import recupere_gf_ga_avec_cache
from resolution_betpawa_precalcul import resout_cotes_betpawa

# On mémorise la vraie fonction (celle qui scrape réellement), puis on
# remplace, uniquement pour ce script, celle utilisée à l'intérieur de
# construit_signaux() par une version qui vérifie d'abord le cache.
# run_pipeline.py lui-même n'est pas modifié -- il continue d'appeler la
# fonction réelle quand il tourne seul (mode panier).
_recupere_gf_ga_reelle = run_pipeline.recupere_gf_ga_avec_repli


def _recupere_gf_ga_avec_cache(url_equipe, nom_equipe, nom_competition, max_matchs=10):
    return recupere_gf_ga_avec_cache(
        _recupere_gf_ga_reelle, url_equipe, nom_equipe, nom_competition, max_matchs
    )


run_pipeline.recupere_gf_ga_avec_repli = _recupere_gf_ga_avec_cache

MODEL_VERSION = "Archetype-v4.3"  # à synchroniser manuellement avec calculs.py
                                   # tant qu'aucun champ de version n'existe
                                   # dans calculs.py lui-même (à ajouter séparément)

FICHIER_MATCHS_DEMAIN = "matchs_demain.json"
FICHIER_MATCHS_SEMAINE = "matchs_semaine.json"
FICHIER_SORTIE = "precalcul.json"
FICHIER_HISTORIQUE = "historique_pronostics.json"  # même fichier que run_pipeline.py


def dates_j2_j3(aujourdhui=None):
    """Retourne les dates ISO de J+2 et J+3 (J+1 vient de matchs_demain.json,
    qui ne contient pas de champ date exploitable de la même façon -- voir
    scraper.py)."""
    aujourdhui = aujourdhui or datetime.date.today()
    return {
        (aujourdhui + datetime.timedelta(days=2)).isoformat(),
        (aujourdhui + datetime.timedelta(days=3)).isoformat(),
    }


def date_j1(aujourdhui=None):
    aujourdhui = aujourdhui or datetime.date.today()
    return (aujourdhui + datetime.timedelta(days=1)).isoformat()


def charge_matchs_fenetre():
    """Construit la liste des matchs J+1/J+2/J+3 à partir des fichiers déjà
    produits par scraper.py (J+1) et scraper_semaine.py (J+2..J+7, filtré ici
    sur J+2/J+3 seulement). Ne relance aucun scraping -- consomme les fichiers
    tels qu'écrits par le run GitHub Actions du jour."""
    matchs_demain = charge_json_ou_vide(FICHIER_MATCHS_DEMAIN, defaut=[])
    matchs_semaine = charge_json_ou_vide(FICHIER_MATCHS_SEMAINE, defaut=[])

    cibles = dates_j2_j3()
    matchs_j2_j3 = [m for m in matchs_semaine if m.get("date") in cibles]

    vus = set()
    fenetre = []
    for m in matchs_demain + matchs_j2_j3:
        mid = m.get("match_id")
        if not mid or mid in vus:
            continue
        vus.add(mid)
        fenetre.append(m)

    return fenetre, len(matchs_demain), len(matchs_j2_j3)


def _slim_pour_archive(s):
    """Version allégée d'un signal pour historique_pronostics.json -- garde
    tout ce qu'il faut pour calculer un ROI et vérifier le résultat plus
    tard, jamais les distributions de probabilité complètes de calculs.py
    (bruit de calcul interne, inutile pour la vérification, coûteux en
    taille de fichier)."""
    return {
        "domicile": s.get("domicile"),
        "exterieur": s.get("exterieur"),
        "competition": s.get("competition"),
        "match_id": s.get("match_id"),
        "date": s.get("date"),
        "heure": s.get("heure"),
        "score": None,
        "verdict_global": s.get("verdict_global"),
        "motif_no_go": s.get("motif_no_go"),
        "confiance": s.get("confiance"),
        "source_cotes": s.get("source_cotes"),
        "betpawa_url": s.get("betpawa_url"),
        "model_version": s.get("model_version"),
        "LISTE_B_liste_finale_apres_correlation": s.get("LISTE_B_liste_finale_apres_correlation"),
    }


def archive_precalcul(signaux, date_j1_iso):
    """N'archive QUE les matchs READY (traite=True, verdict_global calculé)
    ET dont la date est celle de demain (J+1) -- jamais J+2/J+3, pour ne
    jamais archiver le même match plusieurs fois à mesure qu'il avance dans
    la fenêtre au fil des nuits (un match J+3 ce soir redeviendra J+2 demain
    puis J+1 après-demain -- c'est CE run-là, la veille du match, qui
    l'archive, pas les précédents).

    Retourne le nombre de matchs archivés (jamais une affirmation vague de
    succès)."""
    candidats = [
        s for s in signaux
        if s.get("traite") and s.get("verdict_global") and s.get("date") == date_j1_iso
    ]
    if not candidats:
        return 0

    historique = charge_json_ou_vide(FICHIER_HISTORIQUE, defaut=[])
    historique.append({
        "date": date_j1_iso,
        "source": "precalcul_auto",
        "nb_matchs_traites": len(candidats),
        "matchs": [_slim_pour_archive(s) for s in candidats],
    })
    with open(FICHIER_HISTORIQUE, "w", encoding="utf-8") as f:
        json.dump(historique, f, ensure_ascii=False, indent=2)

    return len(candidats)


def main():
    fenetre, nb_demain, nb_j2_j3 = charge_matchs_fenetre()

    if not fenetre:
        print("ATTENTION : aucune matchs_demain.json/matchs_semaine.json "
              "exploitable -- vérifier que scraper.py et scraper_semaine.py "
              "ont bien tourné avant ce script.")

    # AJOUT 01/09/2026 -- modifie fenetre EN PLACE (ajoute cotes_manuelles
    # aux matchs résolus). Ne fait jamais planter le run : toute erreur
    # interne est absorbée dans resout_cotes_betpawa() et se traduit par
    # un compteur, jamais une exception qui remonte ici.
    compteurs_betpawa = resout_cotes_betpawa(fenetre)
    print(f"Résolution Betpawa : {compteurs_betpawa}")

    signaux = construit_signaux(fenetre)

    for s in signaux:
        s["model_version"] = MODEL_VERSION
        s["status"] = "READY" if s.get("traite") else "PARTIAL"
        s["prepared_at"] = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    # AJOUT 02/09/2026 -- ferme la boucle vers verification_resultats.py.
    date_j1_iso = date_j1()
    nb_archives = archive_precalcul(signaux, date_j1_iso)
    print(f"Archivage historique : {nb_archives} match(s) J+1 ({date_j1_iso}) "
          f"ajouté(s) à {FICHIER_HISTORIQUE}.")

    sortie = {
        "genere_le": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "nb_matchs_demain_source": nb_demain,
        "nb_matchs_j2_j3_source": nb_j2_j3,
        "nb_matchs_fenetre": len(fenetre),
        "nb_ready": sum(1 for s in signaux if s["status"] == "READY"),
        "nb_partial": sum(1 for s in signaux if s["status"] == "PARTIAL"),
        "nb_archives_historique": nb_archives,
        "betpawa": compteurs_betpawa,
        "signaux": signaux,
    }

    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, indent=2)

    print(f"{FICHIER_SORTIE} écrit : {sortie['nb_matchs_fenetre']} matchs "
          f"({sortie['nb_ready']} READY, {sortie['nb_partial']} PARTIAL). "
          f"Betpawa : {compteurs_betpawa['betpawa_cotes_extraites']} match(s) "
          f"avec cotes réelles, {compteurs_betpawa['betpawa_tentes']} tenté(s).")

    if not fenetre:
        sys.exit(1)


if __name__ == "__main__":
    main()
