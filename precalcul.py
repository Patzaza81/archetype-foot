"""
precalcul.py -- prépare automatiquement les pronostics de J+1, J+2 et J+3,
indépendamment de tout panier utilisateur.

Ne modifie ni calculs.py ni run_pipeline.py : réutilise construit_signaux()
tel quel (le moteur ne change pas), seule la source des matchs à traiter
change -- au lieu de panier.json (sélection manuelle), on prend directement
matchs_demain.json (J+1) + matchs_semaine.json filtré sur les deux dates
suivantes (J+2, J+3).

Sortie : precalcul.json, liste de signaux au même format que ceux produits
par run_pipeline.py, avec deux champs ajoutés :
  - model_version : identifiant de la version du moteur au moment du calcul
  - status        : READY (traite=True), PARTIAL/FAILED (traite=False,
                    voir raison_non_traite)

Ce script tourne EN PLUS du pipeline existant pour l'instant -- il ne le
remplace pas. Le panier et son déclenchement manuel restent fonctionnels
tant que ce mode n'a pas été validé sur plusieurs cycles réels.

JAMAIS EXÉCUTÉ EN CONDITIONS RÉELLES au moment où ce fichier est écrit --
recupere_details_match() fait des appels réseau vers matchendirect.fr,
indisponibles depuis l'environnement où ce script a été rédigé. Le premier
run réel (GitHub Actions ou local avec accès réseau) est le vrai test.
"""
import datetime
import json
import sys

from run_pipeline import construit_signaux, charge_json_ou_vide

MODEL_VERSION = "Archetype-v4.3"  # à synchroniser manuellement avec calculs.py
                                   # tant qu'aucun champ de version n'existe
                                   # dans calculs.py lui-même (à ajouter séparément)

FICHIER_MATCHS_DEMAIN = "matchs_demain.json"
FICHIER_MATCHS_SEMAINE = "matchs_semaine.json"
FICHIER_SORTIE = "precalcul.json"


def dates_j2_j3(aujourdhui=None):
    """Retourne les dates ISO de J+2 et J+3 (J+1 vient de matchs_demain.json,
    qui ne contient pas de champ date exploitable de la même façon -- voir
    scraper.py)."""
    aujourdhui = aujourdhui or datetime.date.today()
    return {
        (aujourdhui + datetime.timedelta(days=2)).isoformat(),
        (aujourdhui + datetime.timedelta(days=3)).isoformat(),
    }


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


def main():
    fenetre, nb_demain, nb_j2_j3 = charge_matchs_fenetre()

    if not fenetre:
        print("ATTENTION : aucune matchs_demain.json/matchs_semaine.json "
              "exploitable -- vérifier que scraper.py et scraper_semaine.py "
              "ont bien tourné avant ce script.")

    signaux = construit_signaux(fenetre)

    for s in signaux:
        s["model_version"] = MODEL_VERSION
        s["status"] = "READY" if s.get("traite") else "PARTIAL"
        s["prepared_at"] = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    sortie = {
        "genere_le": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "nb_matchs_demain_source": nb_demain,
        "nb_matchs_j2_j3_source": nb_j2_j3,
        "nb_matchs_fenetre": len(fenetre),
        "nb_ready": sum(1 for s in signaux if s["status"] == "READY"),
        "nb_partial": sum(1 for s in signaux if s["status"] == "PARTIAL"),
        "signaux": signaux,
    }

    with open(FICHIER_SORTIE, "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, indent=2)

    print(f"{FICHIER_SORTIE} écrit : {sortie['nb_matchs_fenetre']} matchs "
          f"({sortie['nb_ready']} READY, {sortie['nb_partial']} PARTIAL).")

    if not fenetre:
        sys.exit(1)


if __name__ == "__main__":
    main()
