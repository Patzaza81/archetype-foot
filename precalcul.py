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
historique_pronostics.json une version allégée des matchs READY dont la
date est J+1 -- jamais J+2/J+3, pour ne jamais archiver le même match
plusieurs fois à mesure qu'il avance dans la fenêtre au fil des nuits.

AJOUT 02/09/2026 (2e partie du jour) : precalcul_leger.json -- même
contenu que precalcul.json pour les 3 jours de la fenêtre, MAIS sans les
champs marches (toutes les probabilités par marché) ni lambda (audit du
calcul) -- ce sont eux qui font l'essentiel du poids du fichier (9,2 Mo au
02/09 pour 1574 matchs). Le site (script.js) lit désormais ce fichier
léger, pas precalcul.json, pour rester utilisable en 3G. Conséquence
connue : la section "tous les marchés calculés" et le détail du lambda
n'apparaissent plus dans "voir les détails" sur le site -- le verdict, le
pari recommandé, la cote, l'EV et le tableau LISTE_A restent, eux,
inchangés. precalcul.json (complet) continue d'exister pour l'inspection
manuelle/debug sur GitHub.

Sortie : precalcul.json (complet, inchangé) + precalcul_leger.json (nouveau,
pour le site) + historique_pronostics.json (grossi d'une entrée par date de
match J+1 présente ce soir).

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

_recupere_gf_ga_reelle = run_pipeline.recupere_gf_ga_avec_repli


def _recupere_gf_ga_avec_cache(url_equipe, nom_equipe, nom_competition, max_matchs=10):
    return recupere_gf_ga_avec_cache(
        _recupere_gf_ga_reelle, url_equipe, nom_equipe, nom_competition, max_matchs
    )


run_pipeline.recupere_gf_ga_avec_repli = _recupere_gf_ga_avec_cache

MODEL_VERSION = "Archetype-v4.3"

FICHIER_MATCHS_DEMAIN = "matchs_demain.json"
FICHIER_MATCHS_SEMAINE = "matchs_semaine.json"
FICHIER_SORTIE = "precalcul.json"
FICHIER_SORTIE_LEGER = "precalcul_leger.json"
FICHIER_HISTORIQUE = "historique_pronostics.json"


def dates_j2_j3(aujourdhui=None):
    aujourdhui = aujourdhui or datetime.date.today()
    return {
        (aujourdhui + datetime.timedelta(days=2)).isoformat(),
        (aujourdhui + datetime.timedelta(days=3)).isoformat(),
    }


def date_j1(aujourdhui=None):
    aujourdhui = aujourdhui or datetime.date.today()
    return (aujourdhui + datetime.timedelta(days=1)).isoformat()


def charge_matchs_fenetre():
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
    """Version pour historique_pronostics.json -- encore plus réduite que
    la version site (pas besoin de LISTE_A/raison_non_traite pour un
    match déjà archivé, seulement de quoi calculer un ROI et vérifier)."""
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


def _leger_pour_site(s):
    """Version pour precalcul_leger.json -- tout ce que script.js affiche
    SAUF marches et lambda (les deux champs les plus lourds, utilisés
    seulement par la section 'tous les marchés calculés'/détail du lambda
    dans 'voir les détails')."""
    d = dict(s)
    d.pop("marches", None)
    d.pop("lambda", None)
    return d


def archive_precalcul(signaux, date_j1_iso):
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

    compteurs_betpawa = resout_cotes_betpawa(fenetre)
    print(f"Résolution Betpawa : {compteurs_betpawa}")

    signaux = construit_signaux(fenetre)

    for s in signaux:
        s["model_version"] = MODEL_VERSION
        s["status"] = "READY" if s.get("traite") else "PARTIAL"
        s["prepared_at"] = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    date_j1_iso = date_j1()
    nb_archives = archive_precalcul(signaux, date_j1_iso)
    print(f"Archivage historique : {nb_archives} match(s) J+1 ({date_j1_iso}) "
          f"ajouté(s) à {FICHIER_HISTORIQUE}.")

    genere_le = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    sortie = {
        "genere_le": genere_le,
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

    # AJOUT 02/09/2026 -- version allégée pour le site (voir docstring).
    sortie_legere = {
        "genere_le": genere_le,
        "nb_matchs_fenetre": len(fenetre),
        "nb_ready": sortie["nb_ready"],
        "nb_partial": sortie["nb_partial"],
        "signaux": [_leger_pour_site(s) for s in signaux],
    }
    with open(FICHIER_SORTIE_LEGER, "w", encoding="utf-8") as f:
        json.dump(sortie_legere, f, ensure_ascii=False, indent=2)

    print(f"{FICHIER_SORTIE} écrit : {sortie['nb_matchs_fenetre']} matchs "
          f"({sortie['nb_ready']} READY, {sortie['nb_partial']} PARTIAL). "
          f"{FICHIER_SORTIE_LEGER} écrit en parallèle (sans marches/lambda). "
          f"Betpawa : {compteurs_betpawa['betpawa_cotes_extraites']} match(s) "
          f"avec cotes réelles, {compteurs_betpawa['betpawa_tentes']} tenté(s).")

    if not fenetre:
        sys.exit(1)


if __name__ == "__main__":
    main()
