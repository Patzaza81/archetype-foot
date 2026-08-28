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

# CORRECTIF (26/08ter) : jusqu'ici, seuls 1x2/double_chance/btts/over_under
# (total) alimentaient LISTE_A/LISTE_B -- pas parce que le modèle ne calcule
# pas les autres marchés (calculs.py calcule aussi handicap, over/under par
# équipe, pair/impair, cages inviolées, score exact), mais parce
# qu'aucune source scrapée (matchendirect/Bet365) n'a jamais fourni de cote
# pour ces marchés-là. Avec l'ajout de cotes saisies manuellement (ex.
# Betpawa, qui couvre ces marchés), construit_candidats() est étendu pour
# les exploiter. Aucun effet sur les matchs scrapés : cote_marche() renvoie
# toujours None pour ces clés côté matchendirect/Bet365, donc ces candidats
# restent simplement absents comme avant.
#
# Score exact reste volontairement à part : c'est le marché le plus
# sensible à une erreur de modèle (probabilités individuelles faibles,
# écarts de cote énormes pour une petite erreur d'ajustement de lambda).
# Cohérent avec la décision déjà actée dans TRANSITION.md 13.1 ("calculés
# mais jamais dans LISTE_A/LISTE_B"). Bascule à True si tu veux l'inclure
# après avoir jugé le risque acceptable -- pas une décision technique.
INCLURE_SCORE_EXACT_DANS_ANALYSE = False

# Même logique pour le nombre exact de buts (0,1,2,3,4,5,6+) -- marché
# calculé par calculs.py depuis le début mais jamais branché ici avant le
# 26/08quater. Moins de combinaisons que le score exact (7 contre ~56),
# mais mêmes probabilités individuelles faibles pour les cases centrales.
INCLURE_NOMBRE_EXACT_BUTS_DANS_ANALYSE = False


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

        # CORRECTIF (26/08quinquies) : généralisé pour accepter deux cas --
        # (a) le cas historique : url_match matchendirect présente, match_id
        #     déduit de l'URL si absent (comportement inchangé) ;
        # (b) NOUVEAU : aucune url_match (ex. page dédiée Betpawa, match hors
        #     couverture matchendirect ou non cherché) -- accepté SI
        #     cotes_manuelles ET match_id explicite sont fournis (le frontend
        #     betpawa.js génère ce match_id, voir betpawa.js). Sans URL,
        #     construit_signaux() marquera le match "non traité" avec une
        #     raison explicite (pas de forme/classement/H2H disponibles) --
        #     jamais un plantage, jamais une donnée devinée.
        a_infos_de_base = item.get("domicile") and item.get("exterieur") and item.get("competition")
        a_url = item.get("url_match")
        a_cotes_manuelles = item.get("cotes_manuelles")

        if a_infos_de_base and (a_url or a_cotes_manuelles):
            match_id = item.get("match_id")
            if not match_id and a_url:
                trouve = MATCH_LINK_RE.search(a_url)
                if not trouve:
                    print(f"AVERTISSEMENT panier.json[{i}] ignoré : match_id absent "
                          f"et introuvable depuis l'URL '{a_url}'.")
                    continue
                match_id = trouve.group(2)
            if not match_id:
                print(f"AVERTISSEMENT panier.json[{i}] ignoré : match_id absent et "
                      f"aucune URL matchendirect pour le déduire (entrée sans "
                      f"scraping -- le frontend doit fournir un match_id explicite).")
                continue
            valides.append({
                "domicile": item["domicile"], "exterieur": item["exterieur"],
                "score": item.get("score"), "competition": item["competition"],
                "url_match": a_url, "match_id": match_id,
                "source": item.get("source", "manuel"),
                # CORRECTIF (26/08ter) : cotes saisies à la main (ex. Betpawa),
                # voir GABARIT_COTES_MANUELLES.json. Absent -> comportement
                # identique à avant (scraping matchendirect/Bet365).
                "cotes_manuelles": item.get("cotes_manuelles"),
            })
            continue

        match_id = item.get("match_id")
        if match_id and match_id in index_jour_demain:
            m = dict(index_jour_demain[match_id])
            m["source"] = item.get("source", "liste")
            # Permet aussi de fournir des cotes manuelles pour un match déjà
            # listé aujourd'hui/demain, si on préfère les cotes Betpawa aux
            # cotes Bet365 scrapées pour ce match précis.
            m["cotes_manuelles"] = item.get("cotes_manuelles")
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

    # --- Marchés ajoutés (26/08ter) : voir commentaire sur
    # INCLURE_SCORE_EXACT_DANS_ANALYSE en tête de fichier pour le contexte. ---

    p_handicap = marches_probas.get("handicap", {})
    for ligne_str, probas in p_handicap.items():
        ligne = float(ligne_str)
        cle_cotes = f"handicap_{ligne_str}"
        cote_domicile = cote_marche(cotes_marches, cle_cotes, "domicile")
        if cote_domicile is not None:
            candidats.append({
                "marche": f"Handicap {ligne_str} - Domicile", "condition": lambda x, y, l=ligne: (x + l) > y,
                "probabilite_modele": probas["domicile"], "cote_observee": cote_domicile,
            })
        cote_exterieur = cote_marche(cotes_marches, cle_cotes, "exterieur")
        if cote_exterieur is not None:
            candidats.append({
                "marche": f"Handicap {ligne_str} - Extérieur", "condition": lambda x, y, l=ligne: (x + l) < y,
                "probabilite_modele": probas["exterieur"], "cote_observee": cote_exterieur,
            })

    for cle_probas, libelle, cond_plus in [
        ("over_under_domicile", "Domicile", lambda x, y, l: x > l),
        ("over_under_exterieur", "Extérieur", lambda x, y, l: y > l),
    ]:
        for ligne_str, probas in marches_probas.get(cle_probas, {}).items():
            ligne = float(ligne_str)
            cle_cotes = f"{cle_probas}_{ligne_str}"
            cote_plus = cote_marche(cotes_marches, cle_cotes, "plus")
            if cote_plus is not None:
                candidats.append({
                    "marche": f"Plus de {ligne_str} buts - {libelle}",
                    "condition": lambda x, y, l=ligne, f=cond_plus: f(x, y, l),
                    "probabilite_modele": probas["plus"], "cote_observee": cote_plus,
                })
            cote_moins = cote_marche(cotes_marches, cle_cotes, "moins")
            if cote_moins is not None:
                candidats.append({
                    "marche": f"Moins de {ligne_str} buts - {libelle}",
                    "condition": lambda x, y, l=ligne, f=cond_plus: not f(x, y, l),
                    "probabilite_modele": probas["moins"], "cote_observee": cote_moins,
                })

    p_pi = marches_probas.get("pair_impair", {})
    if p_pi:
        for cle_marche, condition in [
            ("pair", lambda x, y: (x + y) % 2 == 0),
            ("impair", lambda x, y: (x + y) % 2 == 1),
        ]:
            cote = cote_marche(cotes_marches, "pair_impair", cle_marche)
            if cote is not None:
                candidats.append({
                    "marche": f"Total buts - {cle_marche}", "condition": condition,
                    "probabilite_modele": p_pi[cle_marche], "cote_observee": cote,
                })

    for cle_probas, condition_oui, libelle in [
        ("cages_inviolees_domicile", lambda x, y: y == 0, "Domicile"),
        ("cages_inviolees_exterieur", lambda x, y: x == 0, "Extérieur"),
    ]:
        p_ci = marches_probas.get(cle_probas, {})
        if p_ci:
            cote_oui = cote_marche(cotes_marches, cle_probas, "oui")
            if cote_oui is not None:
                candidats.append({
                    "marche": f"Cage inviolée - {libelle}", "condition": condition_oui,
                    "probabilite_modele": p_ci["oui"], "cote_observee": cote_oui,
                })
            cote_non = cote_marche(cotes_marches, cle_probas, "non")
            if cote_non is not None:
                candidats.append({
                    "marche": f"Encaisse au moins 1 but - {libelle}",
                    "condition": lambda x, y, c=condition_oui: not c(x, y),
                    "probabilite_modele": p_ci["non"], "cote_observee": cote_non,
                })

    if INCLURE_SCORE_EXACT_DANS_ANALYSE:
        for score_str, proba in marches_probas.get("score_exact", {}).items():
            x_cible, y_cible = (int(v) for v in score_str.split("-"))
            cote = cote_marche(cotes_marches, "score_exact", score_str)
            if cote is not None:
                candidats.append({
                    "marche": f"Score exact {score_str}",
                    "condition": lambda x, y, xc=x_cible, yc=y_cible: x == xc and y == yc,
                    "probabilite_modele": proba, "cote_observee": cote,
                })

    if INCLURE_NOMBRE_EXACT_BUTS_DANS_ANALYSE:
        for n_str, proba in marches_probas.get("nombre_exact_buts", {}).items():
            cote = cote_marche(cotes_marches, "nombre_exact_buts", n_str)
            if cote is not None:
                if n_str == "6+":
                    condition = lambda x, y: (x + y) >= 6
                else:
                    n_cible = int(n_str)
                    condition = lambda x, y, nc=n_cible: (x + y) == nc
                candidats.append({
                    "marche": f"Nombre exact de buts {n_str}",
                    "condition": condition,
                    "probabilite_modele": proba, "cote_observee": cote,
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

        if not (nom_domicile and nom_exterieur and competition):
            signal["raison_non_traite"] = "donnees_de_base_manquantes"
            resultats.append(signal)
            continue

        if not url_match:
            # CORRECTIF (26/08quinquies) : match sans page matchendirect (ex.
            # ajouté depuis betpawa.html, championnat hors couverture ou URL
            # simplement non cherchée). Les cotes manuelles alimentent l'EV
            # mais ne remplacent pas classement/forme/H2H, nécessaires au
            # calcul de lambda -- rien n'est deviné à la place. Le match
            # reste visible (verdict NO_GO implicite) avec une raison claire,
            # plutôt que d'être traité ou silencieusement perdu.
            signal["raison_non_traite"] = (
                "pas_d_url_matchendirect : forme/classement/H2H indisponibles, "
                "lambda non calculable -- les cotes manuelles seules ne suffisent "
                "pas à faire tourner le modèle Poisson/Dixon-Coles"
            )
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

        cotes_manuelles = m.get("cotes_manuelles")
        cotes_marches = {}
        if cotes_manuelles:
            # CORRECTIF (26/08ter) : cotes saisies à la main (ex. Betpawa) --
            # pas de scraping matchendirect pour ce match. Structure attendue
            # identique à ce que recupere_cotes_marches renvoie (voir
            # GABARIT_COTES_MANUELLES.json). Aucune vérification de fraîcheur
            # ou de cohérence n'est faite ici -- responsabilité de la
            # personne qui saisit les cotes, comme pour tout champ manuel du
            # panier.
            cotes_marches = cotes_manuelles
            signal["source_cotes"] = "manuel"
        else:
            try:
                cotes_marches = recupere_cotes_marches(url_match + "?p=face-a-face")
            except Exception as e:
                signal["avertissement_cotes"] = f"erreur_technique: {e}"
            signal["source_cotes"] = "matchendirect_bet365"

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
        decision = calculs.decision_go_nogo(
            liste_a, liste_b, len(candidats),
            nb_matchs_domicile_utilises=stats_domicile["nb_domicile"],
            nb_matchs_exterieur_utilises=stats_exterieur["nb_exterieur"],
        )

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
        "genere_le": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
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
