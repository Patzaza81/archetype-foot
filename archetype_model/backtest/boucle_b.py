"""
archetype_model/backtest/boucle_b.py — Backtest walk-forward sur les
matchs déjà vérifiés de `historique_pronostics.json` (instruction du
prompt de session du 08/09/2026, appliquée telle quelle).

RÈGLE NON NÉGOCIABLE (donnée explicitement dans le prompt de session) :
le λ déjà stocké dans `historique_pronostics.json` pour chaque match
est un résultat de calcul de l'ANCIEN moteur (Dixon-Coles :
`lambda_home_base`, `modifier_defense_home`, etc.) -- JAMAIS réutilisé
ici, sous aucune forme. Seules les données BRUTES (buts marqués/
encaissés déjà en cache dans `cache_equipes.json`) sont réutilisées ;
les λ sont recalculés en entier avec `poisson.lambda_estimators`
(formules v3 §6). Réutiliser l'ancien λ reviendrait à vérifier que
l'ancien moteur est d'accord avec lui-même, pas à tester le nouveau.

CONTRAINTE RÉSEAU ASSUMÉE, à ne jamais oublier en lisant ce fichier :
la résolution équipe -> clé de cache nécessite l'URL de la page équipe,
qui n'est PAS stockée dans `historique_pronostics.json` (seulement le
nom de l'équipe et l'URL du MATCH). Elle s'obtient via
`scraper_details.recupere_details_match(url_match)`, qui fait un VRAI
appel réseau vers matchendirect.fr à chaque match. Ce module ne peut
donc PAS être exécuté dans un environnement sans accès à ce domaine --
c'est le cas du bac à sable utilisé pour écrire et tester ce fichier.
Conséquence directe et assumée : ce module n'a été testé qu'avec des
données factices (voir les tests associés), jamais en conditions
réelles sur les vrais matchs -- l'exécution réelle doit se faire via
GitHub Actions ou en local, là où matchendirect.fr est accessible.

LIMITE DE DONNÉES ASSUMÉE, également à garder en tête en lisant des
résultats produits par ce module : `cache_equipes.json` a été constitué
par l'ANCIEN scraper (`recupere_gf_ga_avec_repli`) -- fenêtre à 10
matchs (pas 12), avec repli sur la saison précédente en cas
d'insuffisance, et prend les N PREMIERS matchs rencontrés sur la page,
qui sont (vérifié le 08/09/2026 sur captures d'écran réelles) les PLUS
ANCIENS, pas les plus récents. Ce backtest applique donc les nouvelles
formules λ à des fenêtres de matchs sélectionnées selon les anciennes
règles -- limite connue, assumée, documentée ici plutôt que cachée :
aucune autre source de données historiques n'existe pour rejouer ces
matchs autrement.

λ_global (v3 §6) EST calculé ici aussi (08/09/2026) : compétition
UNIQUE (celle du match), domicile+extérieur de chaque équipe fusionnés
-- voir `_stats_globales_depuis_cache`. Possible sans fetch réseau
supplémentaire, `cache_equipes.json` contient déjà les deux listes par
équipe. Ce module ne calcule PAS la robustesse inter-scénarios (voir
main.py pour ça) -- il se concentre sur la comparaison prédiction/
résultat réel par scénario.
"""

import json

from scraper_details import recupere_details_match
from cache_equipes import _cle

from ..data import validation
from ..statistics import team_stats
from ..poisson import lambda_estimators, markets
from ..main import SCENARIOS


def charge_matchs_verifies(chemin_historique="historique_pronostics.json"):
    """Liste plate des matchs de `historique_pronostics.json` qui ont
    un score réel enregistré (score non None) -- exclut les matchs non
    traités. Ne lit QUE domicile/exterieur/competition/score/url_match/
    date/match_id -- aucun champ calculé par l'ancien moteur (lambda,
    marches, verdict_global...) n'est même chargé."""
    with open(chemin_historique, "r", encoding="utf-8") as f:
        jours = json.load(f)
    matchs = []
    for jour in jours:
        for m in jour.get("matchs", []):
            if m.get("score") is not None:
                matchs.append({
                    "domicile": m["domicile"],
                    "exterieur": m["exterieur"],
                    "competition": m["competition"],
                    "score": m["score"],
                    "url_match": m["url_match"],
                    "date": m.get("date"),
                    "match_id": m.get("match_id"),
                })
    return matchs


def resout_urls_equipes(url_match):
    """(url_equipe_domicile, url_equipe_exterieur) via un vrai scraping
    de la page de match -- REQUIERT un accès réseau à matchendirect.fr.
    (None, None) si la page ne fournit pas les deux URLs."""
    details = recupere_details_match(url_match)
    return details.get("url_equipe_domicile"), details.get("url_equipe_exterieur")


def recupere_fenetres_depuis_cache(url_domicile, url_exterieur, competition, cache):
    """Lit `cache` (cache_equipes.json déjà chargé en mémoire) et
    renvoie (fenetre_a, fenetre_b) au format de
    data.validation.classifie_fenetre. (None, None) si l'une des deux
    équipes est absente du cache -- jamais une supposition de données
    manquantes."""
    entree_a = cache.get(_cle(url_domicile, competition))
    entree_b = cache.get(_cle(url_exterieur, competition))
    if entree_a is None or entree_b is None:
        return None, None
    matchs_a_domicile = entree_a["resultat"]["matchs_domicile_bruts"]
    matchs_b_exterieur = entree_b["resultat"]["matchs_exterieur_bruts"]
    return validation.classifie_fenetre(matchs_a_domicile), validation.classifie_fenetre(matchs_b_exterieur)


def _stats_globales_depuis_cache(url_equipe, competition, cache):
    """
    GF/GA pour le scénario "global" (v3 §6) DEPUIS LE CACHE -- même
    principe que main._stats_globales : compétition UNIQUE (celle du
    match), domicile+extérieur de cette équipe fusionnés, PAS plusieurs
    compétitions (décision du 08/09/2026, annule une version
    antérieure qui aurait mélangé plusieurs compétitions).

    Possible sans fetch réseau supplémentaire : `cache_equipes.json`
    contient déjà `matchs_domicile_bruts` ET `matchs_exterieur_bruts`
    pour chaque équipe dans cette compétition -- il suffit de les
    fusionner. (None, None) si l'équipe est absente du cache ou si la
    fenêtre globale est INSUFFISANTE (N<5).
    """
    entree = cache.get(_cle(url_equipe, competition))
    if entree is None:
        return None, None
    matchs_fusionnes = entree["resultat"]["matchs_domicile_bruts"] + entree["resultat"]["matchs_exterieur_bruts"]
    fenetre_globale = validation.classifie_fenetre(matchs_fusionnes)
    if fenetre_globale["statut"] != validation.STATUT_UTILISABLE:
        return None, None
    stats_off = team_stats.stats_offensives(fenetre_globale["matchs_retenus"])
    stats_def = team_stats.stats_defensives(fenetre_globale["matchs_retenus"])
    return stats_off["moyenne"], stats_def["moyenne"]


def _parse_score(score_str):
    """'0-1' -> (0, 1). None si le format est inattendu -- jamais un
    score deviné."""
    try:
        dom, ext = score_str.split("-")
        return int(dom), int(ext)
    except (ValueError, AttributeError, TypeError):
        return None


def evalue_un_match(match_verifie, cache):
    """
    Calcule les prédictions du NOUVEAU moteur pour un match déjà joué
    et les compare au score réel. Un statut explicite est renvoyé à
    chaque point d'échec possible -- jamais une exception qui
    interromprait tout le backtest pour un seul match mal formé,
    absent du cache, ou insuffisant en historique.
    """
    score = _parse_score(match_verifie["score"])
    if score is None:
        return {"statut": "SCORE_ILLISIBLE", "match": match_verifie}

    url_a, url_b = resout_urls_equipes(match_verifie["url_match"])
    if not url_a or not url_b:
        return {"statut": "URL_EQUIPE_INTROUVABLE", "match": match_verifie}

    fenetre_a, fenetre_b = recupere_fenetres_depuis_cache(url_a, url_b, match_verifie["competition"], cache)
    if fenetre_a is None or fenetre_b is None:
        return {"statut": "ABSENT_DU_CACHE", "match": match_verifie}
    if fenetre_a["statut"] != validation.STATUT_UTILISABLE or fenetre_b["statut"] != validation.STATUT_UTILISABLE:
        return {"statut": "INSUFFISANT", "match": match_verifie}

    stats_off_a = team_stats.stats_offensives(fenetre_a["matchs_retenus"])
    stats_def_a = team_stats.stats_defensives(fenetre_a["matchs_retenus"])
    stats_off_b = team_stats.stats_offensives(fenetre_b["matchs_retenus"])
    stats_def_b = team_stats.stats_defensives(fenetre_b["matchs_retenus"])

    gf_a_global, ga_a_global = _stats_globales_depuis_cache(url_a, match_verifie["competition"], cache)
    gf_b_global, ga_b_global = _stats_globales_depuis_cache(url_b, match_verifie["competition"], cache)

    lambdas = lambda_estimators.estime_lambdas(
        gf_a_domicile=stats_off_a["moyenne"], ga_a_domicile=stats_def_a["moyenne"],
        gf_a_global=gf_a_global, ga_a_global=ga_a_global,
        gf_b_exterieur=stats_off_b["moyenne"], ga_b_exterieur=stats_def_b["moyenne"],
        gf_b_global=gf_b_global, ga_b_global=ga_b_global,
    )

    buts_dom_reel, buts_ext_reel = score
    if buts_dom_reel > buts_ext_reel:
        issue_reelle = "domicile"
    elif buts_ext_reel > buts_dom_reel:
        issue_reelle = "exterieur"
    else:
        issue_reelle = "nul"

    predictions_par_scenario = {}
    for scenario in SCENARIOS:
        predictions_par_scenario[scenario] = markets.calcule_tous_les_marches(
            lambdas["A"][scenario], lambdas["B"][scenario]
        )

    return {
        "statut": "OK",
        "match": match_verifie,
        "resultat_reel": {
            "buts_domicile": buts_dom_reel, "buts_exterieur": buts_ext_reel,
            "issue_1x2": issue_reelle, "total_buts": buts_dom_reel + buts_ext_reel,
            "btts": buts_dom_reel > 0 and buts_ext_reel > 0,
        },
        "lambdas": lambdas,
        "predictions_par_scenario": predictions_par_scenario,
    }


def execute_boucle_b(chemin_historique="historique_pronostics.json", chemin_cache="cache_equipes.json"):
    """Point d'entrée. Charge les matchs vérifiés et le cache une seule
    fois, évalue chaque match indépendamment -- un match en échec
    n'interrompt jamais les suivants. REQUIERT un accès réseau à
    matchendirect.fr (voir note en tête de fichier) : n'a jamais été
    exécuté en conditions réelles depuis l'environnement où ce fichier
    a été écrit et testé."""
    matchs = charge_matchs_verifies(chemin_historique)
    with open(chemin_cache, "r", encoding="utf-8") as f:
        cache = json.load(f)
    return [evalue_un_match(m, cache) for m in matchs]


def _brier_score(paires_prob_reel):
    """Score de Brier : moyenne de (probabilité prédite - résultat réel
    binaire 0/1)^2 -- plus bas est meilleur (0 = prédictions parfaites,
    0.25 = pas mieux qu'une pièce non informée sur un événement à 50%).
    None si la liste est vide, jamais une exception."""
    if not paires_prob_reel:
        return None
    return sum((p - r) ** 2 for p, r in paires_prob_reel) / len(paires_prob_reel)


def agrege_resultats(resultats):
    """
    Résumé d'un run de `execute_boucle_b` : comptage par statut (pour
    voir tout de suite combien de matchs sont réellement exploitables
    vs bloqués par quelle raison), et score de Brier du marché
    "victoire domicile" (1X2), un par scénario λ -- calibration
    seulement sur les matchs au statut OK, jamais mélangé avec les
    matchs en échec.

    Ne calcule le Brier que sur le marché 1X2/domicile pour cette
    version -- étendre à BTTS/Over-Under est immédiat (même structure)
    mais pas fait ici, faute de temps (décision du 08/09/2026).
    """
    comptes_statut = {}
    for r in resultats:
        comptes_statut[r["statut"]] = comptes_statut.get(r["statut"], 0) + 1

    matchs_ok = [r for r in resultats if r["statut"] == "OK"]

    brier_par_scenario = {}
    for scenario in SCENARIOS:
        paires = []
        for r in matchs_ok:
            marches_scenario = r["predictions_par_scenario"][scenario]
            p_1x2 = marches_scenario["1x2"]
            if p_1x2 is None:
                continue
            reel = 1 if r["resultat_reel"]["issue_1x2"] == "domicile" else 0
            paires.append((p_1x2["domicile"], reel))
        brier_par_scenario[scenario] = _brier_score(paires)

    return {
        "n_total": len(resultats),
        "comptes_par_statut": comptes_statut,
        "n_matchs_ok": len(matchs_ok),
        "brier_score_victoire_domicile_par_scenario": brier_par_scenario,
    }
