"""
run_pipeline.py — Orchestrateur. Flux MANUEL : ne traite que ce qui est dans
panier.json.

CORRECTIF 26/08 : recupere_cotes_marches ne renvoie plus un tuple
(marches, diagnostics) -- juste le dict des marchés (bookmaker fixe Bet365,
voir scraper_details.py). Suppression du diagnostic "cotes à risque",
devenu sans objet : plus de mode de repli ambigu à surveiller avec une
seule source de cote par marché.
"""
import datetime
import json
import re
from scraper_details import (
    recupere_details_match, recupere_gf_ga_avec_repli, recupere_cotes_marches,
    recupere_classement_du_match, recupere_h2h,
)
import calculs

MAX_MATCHS_HISTORIQUE = 10
FICHIER_MATCHS_DU_JOUR = "matchs_du_jour.json"
FICHIER_MATCHS_DEMAIN = "matchs_demain.json"
FICHIER_PANIER = "panier.json"
FICHIER_HISTORIQUE = "historique_pronostics.json"
MATCH_LINK_RE = re.compile(r"/live-score/([a-z0-9\-]+)_([a-z0-9]+)\.html")


def charge_json_ou_vide(chemin, defaut):
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return defaut


def normalise_panier(panier_brut, matchs_du_jour, matchs_demain):
    index_jour_demain = {
        m["match_id"]: m for m in (matchs_du_jour + matchs_demain) if m.get("match_id")
    }
    valides = []
    for i, item in enumerate(panier_brut):
        if isinstance(item, str):
            item = {"match_id": item}

        a_tous_les_champs_manuels = (
            item.get("url_match") and item.get("domicile")
            and item.get("exterieur") and item.get("competition")
        )
        if a_tous_les_champs_manuels:
            match_id = item.get("match_id")
            if not match_id:
                trouve = MATCH_LINK_RE.search(item["url_match"])
                if not trouve:
                    print(f"AVERTISSEMENT panier.json[{i}] ignoré : match_id absent "
                          f"et introuvable depuis l'URL '{item['url_match']}'.")
                    continue
                match_id = trouve.group(2)
            valides.append({
                "domicile": item["domicile"], "exterieur": item["exterieur"],
                "score": item.get("score"), "competition": item["competition"],
                "url_match": item["url_match"], "match_id": match_id,
                "source": item.get("source", "manuel"),
            })
            continue

        match_id = item.get("match_id")
        if match_id and match_id in index_jour_demain:
            m = dict(index_jour_demain[match_id])
            m["source"] = item.get("source", "liste")
            valides.append(m)
            continue

        print(f"AVERTISSEMENT panier.json[{i}] ignoré : match_id '{match_id}' "
              f"introuvable dans {FICHIER_MATCHS_DU_JOUR} ni {FICHIER_MATCHS_DEMAIN}, "
              f"et champs manuels (url_match/domicile/exterieur/competition) incomplets.")
    return valides


def archive_run(signaux, nb_entrees_panier):
    historique = charge_json_ou_vide(FICHIER_HISTORIQUE, defaut=[])
    historique.append({
        "date": datetime.date.today().isoformat(),
        "nb_entrees_panier": nb_entrees_panier,
        "nb_matchs_traites": len(signaux),
        "matchs": signaux,
    })
    with open(FICHIER_HISTORIQUE, "w", encoding="utf-8") as f:
        json.dump(historique, f, indent=2, ensure_ascii=False)


def cote_marche(cotes_marches, cle_marche, cle_selection):
    """Lit une cote pour un marché/sélection donnés -- remplace
    extrait_cote_min (obsolète, ne s'applique qu'à un panel multi-
    bookmakers). Une seule source désormais : marches[cle][cle_selection],
    déjà None si absente."""
    panel = cotes_marches.get(cle_marche)
    if not panel:
        return None
    return panel.get(cle_selection)


def construit_candidats(marches_probas, cotes_marches):
    candidats = []

    p_1x2 = marches_probas.get("1x2", {})
    if p_1x2:
        for cle_marche, cle_cote, condition in [
            ("1", "1", lambda x, y: x > y),
            ("X", "N", lambda x, y: x == y),
            ("2", "2", lambda x, y: x < y),
        ]:
            cote = cote_marche(cotes_marches, "1x2", cle_cote)
            if cote is not None:
                candidats.append({
                    "marche": f"1X2 - {cle_marche}", "condition": condition,
                    "probabilite_modele": p_1x2[cle_marche], "cote_observee": cote,
                })

    p_dc = marches_probas.get("double_chance", {})
    if p_dc:
        for cle_marche, cle_cote, condition in [
            ("1X", "1N", lambda x, y: x >= y),
            ("12", "12", lambda x, y: x != y),
            ("X2", "N2", lambda x, y: x <= y),
        ]:
            cote = cote_marche(cotes_marches, "double_chance", cle_cote)
            if cote is not None:
                candidats.append({
                    "marche": f"Double chance - {cle_marche}", "condition": condition,
                    "probabilite_modele": p_dc[cle_marche], "cote_observee": cote,
                })

    p_btts = marches_probas.get("btts", {})
    if p_btts:
        for cle_marche, cle_cote, condition in [
            ("oui", "Oui", lambda x, y: x > 0 and y > 0),
            ("non", "Non", lambda x, y: x == 0 or y == 0),
        ]:
            cote = cote_marche(cotes_marches, "btts", cle_cote)
            if cote is not None:
                candidats.append({
                    "marche": f"BTTS - {cle_marche}", "condition": condition,
                    "probabilite_modele": p_btts[cle_marche], "cote_observee": cote,
                })

    p_ou = marches_probas.get("over_under", {})
    for ligne_str, probas in p_ou.items():
        cle_cotes = f"over_under_{ligne_str}"
        ligne = float(ligne_str)
        cote_plus = cote_marche(cotes_marches, cle_cotes, "plus")
        if cote_plus is not None:
            candidats.append({
                "marche": f"Plus de {ligne_str} buts", "condition": lambda x, y, l=ligne: (x + y) > l,
                "probabilite_modele": probas["plus"], "cote_observee": cote_plus,
            })
        cote_moins = cote_marche(cotes_marches, cle_cotes, "moins")
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

        cote_1 = cote_marche(cotes_marches, "1x2", "1")

        lam = calculs.calcule_lambda(
            gf_home, ga_home, gf_away, ga_away,
            ratios_contextuels_home=ratios_home, ratios_contextuels_away=ratios_away,
        )
        matrice = calculs.matrice_poisson_dixon_coles(lam["lambda_home"], lam["lambda_away"])
        proba_1 = calculs.probabilite_marche(matrice, lambda x, y: x > y)
        marches_probas = calculs.construit_probabilites_marches(
            matrice, lignes_ou=(0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5)
        )

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

        candidats = construit_candidats(marches_probas, cotes_marches)
        liste_a = calculs.construit_liste_a(candidats)
        liste_b = calculs.construit_liste_b(liste_a, matrice)
        decision = calculs.decision_go_nogo(liste_a, liste_b, len(candidats))

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
    matchs_demain = charge_json_ou_vide(FICHIER_MATCHS_DEMAIN, defaut=[])
    panier_brut = charge_json_ou_vide(FICHIER_PANIER, defaut=[])

    matchs_a_traiter = normalise_panier(panier_brut, matchs_du_jour, matchs_demain)

    if not matchs_du_jour:
        print(f"ATTENTION : {FICHIER_MATCHS_DU_JOUR} introuvable ou vide.")
    if not panier_brut:
        print(f"{FICHIER_PANIER} vide -- 0 match sera traité.")
    elif not matchs_a_traiter:
        print(f"ATTENTION : {len(panier_brut)} entrée(s) dans {FICHIER_PANIER} mais "
              f"AUCUNE n'a pu être résolue -- panier probablement périmé (oubli de "
              f"mise à jour avant ce run ?) ou entrées mal formées (voir avertissements ci-dessus).")

    signaux = construit_signaux(matchs_a_traiter)

    if matchs_a_traiter:
        archive_run(signaux, len(matchs_a_traiter))
        with open(FICHIER_PANIER, "w", encoding="utf-8") as f:
            json.dump([], f)

    sortie = {
        "genere_le": None,
        "nb_matchs_du_jour_disponibles": len(matchs_du_jour),
        "nb_matchs_demain_disponibles": len(matchs_demain),
        "nb_entrees_panier": len(panier_brut),
        "nb_matchs": len(signaux),
        "matchs": signaux,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(sortie, f, indent=2, ensure_ascii=False)
    print(f"Pipeline terminé : {len(signaux)} matchs traités "
          f"(panier : {len(panier_brut)} entrée(s)) -> data.json")


if __name__ == "__main__":
    main()
