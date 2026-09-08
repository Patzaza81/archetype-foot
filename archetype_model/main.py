"""
archetype_model/main.py — Orchestration d'un match réel : va chercher
l'historique des deux équipes (data.loader), calcule les stats
(statistics.team_stats), les 4 λ (poisson.lambda_estimators), les
matrices et marchés essentiels (poisson.distribution/markets), et la
robustesse par marché (poisson.robustness).

PÉRIMÈTRE ASSUMÉ, décision du 08/09/2026 (contrainte de temps) :
- λ_global est TOUJOURS None ici -- data.loader ne sait pas encore
  agréger "toutes compétitions confondues" (limite déjà documentée
  dans statistics/team_stats.py). Conséquence directe et honnête :
  la robustesse par marché ne peut jamais être STABLE/INSTABLE tant
  que ce chantier n'est pas fait, elle est TOUJOURS INDETERMINE
  (poisson.robustness exige les 4 scénarios présents). Ce n'est pas
  un bug caché, c'est la conséquence mécanique et assumée du choix de
  ne pas coder l'agrégation multi-compétitions dans cette fenêtre de
  temps.
- Marchés calculés : 1X2, Double Chance, BTTS, Over/Under 2.5 total
  (voir poisson/markets.py pour le périmètre réduit assumé).
"""

from .data import loader
from .data import validation
from .statistics import team_stats
from .poisson import lambda_estimators
from .poisson import distribution
from .poisson import markets
from .poisson import robustness

SCENARIOS = ("offensif", "defensif", "contextuel", "global")


def _valeurs_4_scenarios(resultats_par_scenario, extracteur):
    """Rassemble, dans l'ordre fixe des 4 scénarios, la valeur extraite
    par `extracteur` sur chacun -- None si le marché lui-même est None
    pour ce scénario (matrice indisponible)."""
    valeurs = []
    for scenario in SCENARIOS:
        marches = resultats_par_scenario[scenario]
        valeurs.append(extracteur(marches))
    return valeurs


def analyse_match(url_domicile, nom_domicile, url_exterieur, nom_exterieur, nom_competition):
    """
    Analyse complète d'un match A (domicile) contre B (extérieur).

    Retourne un dict avec au minimum la clé "statut" :
    - "INSUFFISANT" si l'une des deux équipes n'a pas assez de matchs
      exploitables (v3 §4.2, N<5) dans la fenêtre pertinente
      (domicile pour A, extérieur pour B) -- dans ce cas, aucune autre
      clé n'est présente, ne jamais lire "lambdas"/"marches" sans
      vérifier le statut d'abord.
    - "OK" sinon, avec "fenetres" (diagnostic des fenêtres utilisées),
      "lambdas", "marches_par_scenario", "robustesse_par_marche".
    """
    historique_domicile = loader.recupere_historique_saison_courante(url_domicile, nom_competition, nom_domicile)
    historique_exterieur = loader.recupere_historique_saison_courante(url_exterieur, nom_competition, nom_exterieur)

    matchs_dom_domicile, _ = loader.separe_domicile_exterieur(historique_domicile)
    _, matchs_ext_exterieur = loader.separe_domicile_exterieur(historique_exterieur)

    fenetre_a = validation.classifie_fenetre(matchs_dom_domicile)
    fenetre_b = validation.classifie_fenetre(matchs_ext_exterieur)

    if fenetre_a["statut"] != validation.STATUT_UTILISABLE or fenetre_b["statut"] != validation.STATUT_UTILISABLE:
        return {"statut": "INSUFFISANT", "fenetres": {"A": fenetre_a, "B": fenetre_b}}

    stats_off_a = team_stats.stats_offensives(fenetre_a["matchs_retenus"])
    stats_def_a = team_stats.stats_defensives(fenetre_a["matchs_retenus"])
    stats_off_b = team_stats.stats_offensives(fenetre_b["matchs_retenus"])
    stats_def_b = team_stats.stats_defensives(fenetre_b["matchs_retenus"])

    lambdas = lambda_estimators.estime_lambdas(
        gf_a_domicile=stats_off_a["moyenne"], ga_a_domicile=stats_def_a["moyenne"],
        gf_a_global=None, ga_a_global=None,  # voir note de périmètre en tête de fichier
        gf_b_exterieur=stats_off_b["moyenne"], ga_b_exterieur=stats_def_b["moyenne"],
        gf_b_global=None, ga_b_global=None,
    )

    marches_par_scenario = {}
    for scenario in SCENARIOS:
        la = lambdas["A"][scenario]
        lb = lambdas["B"][scenario]
        matrice = distribution.matrice_scores(la, lb)
        marches_par_scenario[scenario] = {
            "1x2": markets.probabilites_1x2(matrice),
            "double_chance": markets.probabilites_double_chance(matrice),
            "btts": markets.probabilite_btts(matrice),
            "over_under_2_5": markets.probabilites_over_under_total(matrice, 2.5),
        }

    def _extrait_1x2(issue):
        return lambda m: m["1x2"][issue] if m["1x2"] else None

    robustesse_par_marche = {
        "1x2_domicile": robustness.evalue_robustesse(_valeurs_4_scenarios(marches_par_scenario, _extrait_1x2("domicile"))),
        "1x2_nul": robustness.evalue_robustesse(_valeurs_4_scenarios(marches_par_scenario, _extrait_1x2("nul"))),
        "1x2_exterieur": robustness.evalue_robustesse(_valeurs_4_scenarios(marches_par_scenario, _extrait_1x2("exterieur"))),
        "btts": robustness.evalue_robustesse(
            _valeurs_4_scenarios(marches_par_scenario, lambda m: m["btts"])),
        "over_2_5": robustness.evalue_robustesse(
            _valeurs_4_scenarios(marches_par_scenario, lambda m: m["over_under_2_5"]["over"] if m["over_under_2_5"] else None)),
    }

    return {
        "statut": "OK",
        "fenetres": {"A": fenetre_a, "B": fenetre_b},
        "lambdas": lambdas,
        "marches_par_scenario": marches_par_scenario,
        "robustesse_par_marche": robustesse_par_marche,
    }
