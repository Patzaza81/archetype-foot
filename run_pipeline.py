"""
run_pipeline.py — Orchestrateur. Flux MANUEL, ne traite que
matchs_selectionnes.json.

ÉTAPES 1/5/6/7 DE L'INVENTAIRE (25/08) : cotes étendues à tous les marchés
over/under scrapables (scraper_details.py), évaluation EV sur TOUS les
marchés disposant à la fois d'une probabilité modèle et d'une cote réelle
(pas seulement 1x2), filtre de corrélation mécanique (LISTE_A -> LISTE_B),
verdict GO/NO_GO. Handicap 3 voies et marchés mi-temps EXCLUS (décision
explicite). Rotation continentale EXCLUE. L'ANCIEN format de sortie
(traite/lambda/marches/cote_1/ev_victoire_domicile/standout) est CONSERVÉ
tel quel en plus des nouveaux champs -- script.js n'est pas encore adapté
au nouveau format (Module 4, chantier séparé), on ne casse pas l'affichage
actuel en ajoutant les nouveaux champs à côté.
"""
import json
from scraper_details import (
    recupere_details_match, recupere_gf_ga_avec_repli, recupere_cotes_marches,
    recupere_classement_du_match, recupere_h2h,
)
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
    if not ids_selectionnes:
        return []
    ids_set = set(ids_selectionnes)
    return [m for m in matchs_bruts if m.get("match_id") in ids_set]


def extrait_cote_min(panel, cle):
    if not panel:
        return None
    valeurs = [ligne[cle] for ligne in panel if cle in ligne and ligne[cle]]
    return min(valeurs) if valeurs else None


def construit_candidats(marches_probas, cotes_marches):
    """
    Construit la liste brute de candidats (avant Étapes 1-2-4 Module 3) sur
    TOUS les marchés disposant à la fois d'une probabilité modèle et d'une
    cote réelle scrapée. Handicap et mi-temps exclus (non scrapés / hors
    scope). Chaque candidat porte sa "condition" (fonction (x,y)->bool) pour
    permettre le calcul de corrélation exact sur la matrice.
    """
    candidats = []

    p_1x2 = marches_probas.get("1x2", {})
    c_1x2 = cotes_marches.get("1x2")
    if p_1x2 and c_1x2:
        for cle_marche, cle_cote, condition in [
            ("1", "1", lambda x, y: x > y),
            ("X", "N", lambda x, y: x == y),
            ("2", "2", lambda x, y: x < y),
        ]:
            cote = extrait_cote_min(c_1x2, cle_cote)
            if cote is not None:
                candidats.append({
                    "marche": f"1X2 - {cle_marche}", "condition": condition,
                    "probabilite_modele": p_1x2[cle_marche], "cote_observee": cote,
                })

    p_dc = marches_probas.get("double_chance", {})
    c_dc = cotes_marches.get("double_chance")
    if p_dc and c_dc:
        for cle_marche, cle_cote, condition in [
            ("1X", "1N", lambda x, y: x >= y),
            ("12", "12", lambda x, y: x != y),
            ("X2", "N2", lambda x, y: x <= y),
        ]:
            cote = extrait_cote_min(c_dc, cle_cote)
            if cote is not None:
                candidats.append({
                    "marche": f"Double chance - {cle_marche}", "condition": condition,
                    "probabilite_modele": p_dc[cle_marche], "cote_observee": cote,
                })

    p_btts = marches_probas.get("btts", {})
    c_btts = cotes_marches.get("btts")
    if p_btts and c_btts:
        for cle_marche, cle_cote, condition in [
            ("oui", "Oui", lambda x, y: x > 0 and y > 0),
            ("non", "Non", lambda x, y: x == 0 or y == 0),
        ]:
            cote = extrait_cote_min(c_btts, cle_cote)
            if cote is not None:
                candidats.append({
                    "marche": f"BTTS - {cle_marche}", "condition": condition,
                    "probabilite_modele": p_btts[cle_marche], "cote_observee": cote,
                })

    p_ou = marches_probas.get("over_under", {})
    for ligne_str, probas in p_ou.items():
        cle_cotes = f"over_under_{ligne_str}"
        panel = cotes_marches.get(cle_cotes)
        if not panel:
            continue
        ligne = float(ligne_str)
        cote_plus = extrait_cote_min(panel, "plus")
        if cote_plus is not None:
            candidats.append({
                "marche": f"Plus de {ligne_str} buts", "condition": lambda x, y, l=ligne: (x + y) > l,
                "probabilite_modele": probas["plus"], "cote_observee": cote_plus,
            })
        cote_moins = extrait_cote_min(panel, "moins")
        if cote_moins is not None:
            candidats.append({
                "marche": f"Moins de {ligne_str} buts", "condition": lambda x, y, l=ligne: (x + y) < l,
                "probabilite_modele": probas["moins"], "cote_observee": cote_moins,
            })

    return candidats


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

        ratio_classement_home = ratio_classement_away = 0.0
        try:
            classement = recupere_classement_du_match(url_match)
            ratio_classement_home = calculs.calcule_ratio_classement(classement, nom_domicile, nom_exterieur)
            ratio_classement_away = -ratio_classement_home
        except Exception as e:
            signal["avertissement_classement"] = f"erreur_technique: {e}"

        ratio_h2h_home = ratio_h2h_away = 0.0
        historique_h2h_brut = []
        try:
            historique_h2h_brut = recupere_h2h(url_match + "?p=face-a-face")
            ratio_h2h_home = calculs.calcule_ratio_h2h(historique_h2h_brut, nom_domicile, nom_exterieur)
            ratio_h2h_away = -ratio_h2h_home
        except Exception as e:
            signal["avertissement_h2h"] = f"erreur_technique: {e}"

        ratios_home = {"classement": ratio_classement_home, "h2h": ratio_h2h_home}
        ratios_away = {"classement": ratio_classement_away, "h2h": ratio_h2h_away}

        cotes_marches = {}
        try:
            cotes_marches = recupere_cotes_marches(url_match + "?p=face-a-face")
        except Exception as e:
            signal["avertissement_cotes"] = f"erreur_technique: {e}"

        cote_1 = extrait_cote_min(cotes_marches.get("1x2"), "1")

        lam = calculs.calcule_lambda(
            gf_home, ga_home, gf_away, ga_away,
            ratios_contextuels_home=ratios_home, ratios_contextuels_away=ratios_away,
        )
        matrice = calculs.matrice_poisson_dixon_coles(lam["lambda_home"], lam["lambda_away"])
        proba_1 = calculs.probabilite_marche(matrice, lambda x, y: x > y)
        # CORRECTIF AUDIT (25/08) : lignes_ou explicite -- le défaut de
        # construit_probabilites_marches s'arrête à 4.5, alors que
        # recupere_cotes_marches scrape jusqu'à 7.5. Sans cet argument, les
        # cotes 5.5/6.5/7.5 scrapées n'avaient jamais de contrepartie
        # modèle et étaient silencieusement ignorées par construit_candidats.
        marches_probas = calculs.construit_probabilites_marches(
            matrice, lignes_ou=(0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5)
        )

        # --- Ancien format conservé tel quel (script.js actuel en dépend) ---
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
        signal["marches"] = marches_probas

        # --- Nouveau format GO/NO_GO (Module 3, Étapes 1-2-4-6-7) ---
        candidats = construit_candidats(marches_probas, cotes_marches)
        liste_a = calculs.construit_liste_a(candidats)
        liste_b = calculs.construit_liste_b(liste_a, matrice)
        decision = calculs.decision_go_nogo(liste_a, liste_b, len(candidats))

        # Kelly appliqué uniquement à LISTE_B (Étape 7), condition non
        # sérialisable en JSON -> retirée avant écriture.
        def serialise(c):
            return {
                "marche": c["marche"], "ev_brut": c["ev_brut"],
                "cote_observee": c["cote_observee"], "probabilite_modele": c["probabilite_modele"],
                "mise_pct_bankroll": calculs.kelly_stake(c["probabilite_modele"], c["cote_observee"]),
            }

        signal["verdict_global"] = decision["verdict_global"]
        signal["motif_no_go"] = decision["motif_no_go"]
        signal["LISTE_A_marches_passant_EV_et_cote"] = [serialise(c) for c in liste_a]
        signal["LISTE_B_liste_finale_apres_correlation"] = [serialise(c) for c in liste_b]
        signal["coefficients_empiriques"] = False

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
