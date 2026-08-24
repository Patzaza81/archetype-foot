"""
run_pipeline.py — Orchestrateur. Flux MANUEL : le pipeline ne traite que les
matchs listés dans matchs_selectionnes.json (édité à la main via
selection.html), pas tous les matchs du jour.

BRANCHEMENT cote_1 (25/08) : ajout de recupere_cotes_marches pour peupler
cote_1 automatiquement -- jusqu'ici toujours None, donc ev_victoire_domicile
et mise_kelly_victoire_domicile n'étaient JAMAIS calculés malgré un modèle
fonctionnel. Choix du bookmaker de référence : MINIMUM du panel observé
(betclic/unibet/winamax/bet365/pmu) -- Betpawa (bookmaker réellement utilisé
pour les paris) n'apparaît dans aucun panel matchendirect observé jusqu'ici ;
ses cotes sont structurellement plus basses (bonus). Le minimum du panel est
l'approximation la plus prudente disponible, PAS une garantie de correspondre
à la vraie cote Betpawa -- à traiter comme majorant, pas comme valeur exacte,
tant qu'aucune comparaison directe n'a été faite.

selection.html/selection.js NON touchés dans ce commit -- une seule chose à
la fois, comme convenu.
"""
import json
from scraper_details import recupere_details_match, recupere_gf_ga_avec_repli, recupere_cotes_marches
import calculs

MAX_MATCHS_HISTORIQUE = 10
FICHIER_MATCHS_DU_JOUR = "matchs_du_jour.json"
FICHIER_SELECTION = "matchs_selectionnes.json"


def charge_json_ou_vide(chemin, defaut):
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return defaut


def filtre_par_selection(matchs_bruts, ids_selectionnes):
    """Ne garde que les matchs dont match_id est dans la sélection.
    Format de matchs_selectionnes.json : liste de match_id (chaînes),
    inchangé -- pas de format alternatif introduit ici."""
    if not ids_selectionnes:
        return []
    ids_set = set(ids_selectionnes)
    return [m for m in matchs_bruts if m.get("match_id") in ids_set]


def extrait_cote_1_min(cotes_marches):
    """
    Retourne le minimum de la cote "1" (victoire domicile) sur le panel de
    bookmakers du marché 1x2, ou None si le marché est introuvable/vide.
    Voir note en tête de fichier sur le choix du minimum (approximation
    Betpawa).
    """
    panel = cotes_marches.get("1x2") if cotes_marches else None
    if not panel:
        return None
    valeurs = [ligne["1"] for ligne in panel if "1" in ligne and ligne["1"]]
    return min(valeurs) if valeurs else None


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

        # Branchement cote_1 -- nouveau. Best-effort assumé : un échec ici ne
        # doit jamais bloquer le calcul du modèle, seulement priver le match
        # de la partie EV/Kelly (déjà le comportement pour cote_1 absente).
        cote_1 = None
        try:
            cotes = recupere_cotes_marches(url_match + "?p=face-a-face")
            cote_1 = extrait_cote_1_min(cotes)
        except Exception as e:
            signal["avertissement_cotes"] = f"erreur_technique: {e}"

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
        signal["cote_1"] = cote_1

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
        print(f"ATTENTION : {FICHIER_MATCHS_DU_JOUR} introuvable ou vide.")
    if not selection:
        print(f"Aucune sélection dans {FICHIER_SELECTION} -- 0 match sera traité.")

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
