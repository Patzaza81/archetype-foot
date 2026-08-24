"""
run_pipeline.py — Orchestrateur. Flux MANUEL (25/08) : le pipeline ne traite
plus automatiquement tous les matchs du jour. Il lit matchs_selectionnes.json
(liste de match_id, éditée à la main via la page de sélection du site) et
n'enrichit QUE ces matchs-là. Le cron quotidien de pipeline.yml continue de
tourner mais devient décoratif tant qu'aucune sélection n'est à jour :
sélection vide ou absente -> data.json avec 0 match traité, pas une erreur.

Le scraping brut (liste complète des matchs du jour, ~150-200, pour
alimenter la page de sélection) est fait SÉPARÉMENT par scraper.py ->
matchs_du_jour.json, AVANT ce script, dans pipeline.yml. Ce script ne
rescrape pas la liste brute lui-même — il la relit depuis ce fichier pour
éviter un second fetch de /live-foot/ inutile.
"""
import json
from scraper_details import recupere_details_match, recupere_gf_ga_avec_repli
import calculs

MAX_MATCHS_HISTORIQUE = 10
FICHIER_MATCHS_DU_JOUR = "matchs_du_jour.json"
FICHIER_SELECTION = "matchs_selectionnes.json"


def charge_json_ou_vide(chemin, defaut):
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Fichier absent ou vide -> comportement par défaut, jamais une
        # erreur qui ferait planter tout le run.
        return defaut


def filtre_par_selection(matchs_bruts, ids_selectionnes):
    if not ids_selectionnes:
        return []
    ids_set = set(ids_selectionnes)
    return [m for m in matchs_bruts if m.get("match_id") in ids_set]


def construit_signaux(matchs_bruts):
    resultats = []

    for m in matchs_bruts:
        url_match = m.get("url_match")
        nom_domicile = m.get("domicile")
        nom_exterieur = m.get("exterieur")
        competition = m.get("competition")

        signal = {**m, "traite": False}

        if not (url_match and nom_domicile and nom_exterieur and competition):
            signal["raison_non_traite"] = "donnees_de_base_manquantes"
            resultats.append(signal)
            continue

        try:
            details = recupere_details_match(url_match)
        except Exception as e:
            signal["raison_non_traite"] = f"erreur_technique: {e}"
            resultats.append(signal)
            continue

        url_eq_domicile = details.get("url_equipe_domicile")
        url_eq_exterieur = details.get("url_equipe_exterieur")
        if not url_eq_domicile or not url_eq_exterieur:
            signal["raison_non_traite"] = "url_equipe_introuvable_sur_page_match"
            resultats.append(signal)
            continue

        try:
            stats_domicile = recupere_gf_ga_avec_repli(
                url_eq_domicile, nom_domicile, competition, max_matchs=MAX_MATCHS_HISTORIQUE
            )
            stats_exterieur = recupere_gf_ga_avec_repli(
                url_eq_exterieur, nom_exterieur, competition, max_matchs=MAX_MATCHS_HISTORIQUE
            )
        except Exception as e:
            signal["raison_non_traite"] = f"erreur_technique: {e}"
            resultats.append(signal)
            continue

        if "raison_non_traite" in stats_domicile:
            signal["raison_non_traite"] = f"domicile: {stats_domicile['raison_non_traite']}"
            resultats.append(signal)
            continue
        if "raison_non_traite" in stats_exterieur:
            signal["raison_non_traite"] = f"exterieur: {stats_exterieur['raison_non_traite']}"
            resultats.append(signal)
            continue

        gf_home = stats_domicile.get("gf_domicile")
        ga_home = stats_domicile.get("ga_domicile")
        gf_away = stats_exterieur.get("gf_exterieur")
        ga_away = stats_exterieur.get("ga_exterieur")

        if None in (gf_home, ga_home, gf_away, ga_away):
            signal["raison_non_traite"] = "historique_domicile_ou_exterieur_vide"
            resultats.append(signal)
            continue

        cote_1 = m.get("cote_1")
        lam = calculs.calcule_lambda(gf_home, ga_home, gf_away, ga_away)
        matrice = calculs.matrice_poisson_dixon_coles(lam["lambda_home"], lam["lambda_away"])
        proba_1 = calculs.probabilite_marche(matrice, lambda x, y: x > y)

        signal["lambda"] = lam
        signal["probabilite_victoire_domicile"] = proba_1
        signal["traite"] = True
        signal["confiance"] = calculs.confiance_lambda(
            min(stats_domicile["nb_domicile"], stats_exterieur["nb_exterieur"])
        )
        signal["nb_matchs_domicile_utilises"] = stats_domicile["nb_domicile"]
        signal["nb_matchs_exterieur_utilises"] = stats_exterieur["nb_exterieur"]

        if cote_1:
            signal["ev_victoire_domicile"] = calculs.calcule_ev(proba_1, cote_1)
            signal["mise_kelly_victoire_domicile"] = calculs.kelly_stake(proba_1, cote_1)
            signal["standout"] = calculs.est_standout(proba_1, cote_1)
        signal["marches"] = calculs.construit_probabilites_marches(matrice)

        resultats.append(signal)

    return resultats


def main():
    matchs_du_jour = charge_json_ou_vide(FICHIER_MATCHS_DU_JOUR, defaut=[])
    selection = charge_json_ou_vide(FICHIER_SELECTION, defaut=[])

    matchs_a_traiter = filtre_par_selection(matchs_du_jour, selection)

    if not matchs_du_jour:
        print(f"ATTENTION : {FICHIER_MATCHS_DU_JOUR} introuvable ou vide -- "
              f"a-t-il bien été généré avant cette étape dans le workflow ?")
    if not selection:
        print(f"Aucune sélection dans {FICHIER_SELECTION} -- 0 match sera traité "
              f"(comportement normal si aucune sélection n'a encore été faite aujourd'hui).")

    signaux = construit_signaux(matchs_a_traiter)
    sortie = {
        "genere_le": None,
        "nb_matchs_du_jour_disponibles": len(matchs_du_jour),
        "nb_matchs_selectionnes": len(selection),
        "nb_matchs": len(signaux),
        "matchs": signaux,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(sortie, f, indent=2, ensure_ascii=False)
    print(f"Pipeline terminé : {len(signaux)} matchs traités sur {len(selection)} sélectionnés -> data.json")


if __name__ == "__main__":
    main()
