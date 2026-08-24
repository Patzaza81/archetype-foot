"""
run_pipeline.py — Orchestrateur quotidien. TOUT À LA RACINE DU DÉPÔT,
volontairement — aucun dossier pipeline/ nécessaire. Seule contrainte réelle
de GitHub : .github/workflows/pipeline.yml doit rester à cet emplacement
précis, ça ne se discute pas. Tout le reste vit à côté de index.html, comme
les fichiers déjà uploadés avec succès.
Écrit data.json à la racine — lu directement par index.html/script.js.

BRANCHEMENT GF/GA v2 (25/08) : remplace l'usage de recupere_classement_du_match
(moyenne saison agrégée, pas de split domicile/extérieur) par
recupere_gf_ga_avec_repli — vrais derniers matchs domicile/extérieur, avec
repli sur la saison précédente UNIQUEMENT si la compétition est identique
(garde-fou promotion/relégation, TRANSITION.md 9.2). Aucun match amical
utilisé dans le calcul. `raison_non_traite` explique chaque échec, remplace
l'ancien champ `erreur_classement`.
"""
import json
from scraper import scrape_programme_du_jour
from scraper_details import recupere_details_match, recupere_gf_ga_avec_repli
import calculs

MAX_MATCHS_HISTORIQUE = 10


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
            # L'équipe n'a aucun match dans le contexte demandé (ex. aucun
            # match extérieur joué du tout) même après repli saison
            # précédente -> pas de valeur devinée.
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
    matchs = scrape_programme_du_jour(max_matchs=20)
    signaux = construit_signaux(matchs)
    sortie = {
        "genere_le": None,
        "nb_matchs": len(signaux),
        "matchs": signaux,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(sortie, f, indent=2, ensure_ascii=False)
    print(f"Pipeline terminé : {len(signaux)} matchs -> data.json")


if __name__ == "__main__":
    main()
