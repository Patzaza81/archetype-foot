"""
archetype_model/main.py — Orchestration d'un match réel : va chercher
l'historique des deux équipes (data.loader), calcule les stats
(statistics.team_stats), les 4 λ (poisson.lambda_estimators), les
matrices et marchés (poisson.distribution/markets), et la robustesse
par marché (poisson.robustness).

λ_global (v3 §6) EST calculé ici, mais UNIQUEMENT sur la compétition du
match analysé (domicile + extérieur mélangés) -- PAS "toutes
compétitions confondues" comme une première version le faisait :
annulé le 08/09/2026, décision explicite de Patrick ("on reste sur les
matchs de championnat"). Voir `_stats_globales` ci-dessous et l'en-tête
de data/loader.py pour l'historique de cette décision.

PÉRIMÈTRE ASSUMÉ restant, décision du 08/09/2026 (contrainte de temps) :
- Marchés calculés : TOUS ceux couverts par poisson.markets.calcule_tous_les_marches
  (1X2, Double Chance, BTTS, Over/Under total, buts par équipe,
  Handicap au quart de but, combos DC+Total) -- voir poisson/markets.py
  pour le détail et les lignes par défaut assumées.
- Robustesse calculée seulement sur un sous-ensemble (1X2 x3, BTTS,
  Over/Under 2.5) -- l'étendre à tous les nouveaux marchés (handicap,
  combos, buts par équipe) n'est pas fait ici, faute de temps ; la
  structure (_valeurs_4_scenarios + extracteur) est générique et se
  réutilise directement pour n'importe quel marché.
- `backtest.boucle_b` calcule maintenant λ_global de la même façon
  (compétition unique, domicile+extérieur fusionnés) -- possible sans
  fetch supplémentaire car `cache_equipes.json` contient déjà les deux
  listes par équipe pour cette compétition.
"""

from .data import loader
from .data import validation
from .statistics import team_stats
from .poisson import lambda_estimators
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


def _stats_globales(historique_complet_equipe):
    """
    GF/GA pour le scénario "global" (v3 §6) -- calculé sur la même
    compétition que les autres scénarios (décision du 08/09/2026,
    annule une version antérieure qui agrégeait plusieurs compétitions,
    voir data/loader.py et data/validation.py pour l'historique de
    cette décision). "Global" ici veut dire : TOUS les matchs de
    l'équipe dans cette compétition, domicile ET extérieur mélangés
    -- contrairement aux scénarios offensif/défensif qui isolent l'un
    ou l'autre.

    `historique_complet_equipe` est la liste COMPLÈTE (non séparée par
    domicile.loader.separe_domicile_exterieur) déjà récupérée par
    `analyse_match` -- aucun fetch réseau supplémentaire ici.

    Retourne (None, None) si la fenêtre est INSUFFISANTE (N<5) --
    lambda_estimators gère déjà nativement un GF/GA à None (le
    scénario global devient None sans affecter les 3 autres)."""
    fenetre_globale = validation.classifie_fenetre(historique_complet_equipe)
    if fenetre_globale["statut"] != validation.STATUT_UTILISABLE:
        return None, None
    stats_off = team_stats.stats_offensives(fenetre_globale["matchs_retenus"])
    stats_def = team_stats.stats_defensives(fenetre_globale["matchs_retenus"])
    return stats_off["moyenne"], stats_def["moyenne"]


def analyse_match(url_domicile, nom_domicile, url_exterieur, nom_exterieur, nom_competition):
    """
    Analyse complète d'un match A (domicile) contre B (extérieur).

    Retourne un dict avec au minimum la clé "statut" :
    - "INSUFFISANT" si l'une des deux équipes n'a pas assez de matchs
      exploitables (v3 §4.2, N<5) dans la fenêtre pertinente
      (domicile pour A, extérieur pour B) -- dans ce cas, aucune autre
      clé n'est présente, ne jamais lire "lambdas"/"marches" sans
      vérifier le statut d'abord. Note : l'insuffisance de la fenêtre
      GLOBALE seule ne bloque PAS le match (elle rend juste λ_global
      None pour l'équipe concernée, voir _stats_globales).
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

    gf_a_global, ga_a_global = _stats_globales(historique_domicile)
    gf_b_global, ga_b_global = _stats_globales(historique_exterieur)

    lambdas = lambda_estimators.estime_lambdas(
        gf_a_domicile=stats_off_a["moyenne"], ga_a_domicile=stats_def_a["moyenne"],
        gf_a_global=gf_a_global, ga_a_global=ga_a_global,
        gf_b_exterieur=stats_off_b["moyenne"], ga_b_exterieur=stats_def_b["moyenne"],
        gf_b_global=gf_b_global, ga_b_global=ga_b_global,
    )

    marches_par_scenario = {}
    for scenario in SCENARIOS:
        la = lambdas["A"][scenario]
        lb = lambdas["B"][scenario]
        marches_par_scenario[scenario] = markets.calcule_tous_les_marches(la, lb)

    def _extrait_1x2(issue):
        return lambda m: m["1x2"][issue] if m["1x2"] else None

    robustesse_par_marche = {
        "1x2_domicile": robustness.evalue_robustesse(_valeurs_4_scenarios(marches_par_scenario, _extrait_1x2("domicile"))),
        "1x2_nul": robustness.evalue_robustesse(_valeurs_4_scenarios(marches_par_scenario, _extrait_1x2("nul"))),
        "1x2_exterieur": robustness.evalue_robustesse(_valeurs_4_scenarios(marches_par_scenario, _extrait_1x2("exterieur"))),
        "btts": robustness.evalue_robustesse(
            _valeurs_4_scenarios(marches_par_scenario, lambda m: m["btts"])),
        "over_2_5": robustness.evalue_robustesse(
            _valeurs_4_scenarios(marches_par_scenario, lambda m: m["over_under_total"][2.5]["over"] if m["over_under_total"][2.5] else None)),
    }

    return {
        "statut": "OK",
        "fenetres": {"A": fenetre_a, "B": fenetre_b},
        "lambdas": lambdas,
        "marches_par_scenario": marches_par_scenario,
        "robustesse_par_marche": robustesse_par_marche,
    }
