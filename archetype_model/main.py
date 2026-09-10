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
from .data import odds_provider
from .statistics import team_stats
from .poisson import lambda_estimators
from .poisson import markets
from .poisson import robustness
from .h2h import h2h_stats
from .h2h import h2h_markets
from .signals import statistiques_signal
from .signals import convergence
from .signals import deduplication
from .signals import selector
from .edv import calculator as edv_calculator

SCENARIOS = ("offensif", "defensif", "contextuel", "global")

# Scénario représentatif utilisé (1) pour comparer au H2H -- convention déjà
# documentée dans h2h_markets.py ("pour l'instant, seul le scénario λ
# 'offensif' ... doit être passé ici") -- et (2) pour représenter
# edge/edv/probabilité du candidat final dans analyse_match_complet().
# Choix V1 en l'absence d'un "scénario retenu" officiel dans le v3 (voir
# signals/convergence.py, décision du 09/09/2026 : aucun scénario officiel
# n'existe, le filtre exige l'unanimité des 4 -- mais UN scénario doit être
# désigné pour porter les valeurs affichées d'un candidat une fois éligible).
# À AJUSTER SI LE v3 PRÉCISE AUTRE CHOSE.
SCENARIO_REPRESENTATIF = "offensif"


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
    - "INSUFFISANT" si l'une des deux équipes a moins de 5 matchs au
      TOTAL cette saison, dans cette compétition (domicile+extérieur
      confondus) -- CORRECTIF du 09/09/2026 (décision explicite de
      Patrick) : la version précédente gatait séparément sur le
      sous-ensemble domicile-seul (pour A) / extérieur-seul (pour B),
      ce qui bloquait à tort des équipes ayant largement assez de
      matchs au total mais peu dans un rôle précis (ex. 5 matchs
      saison dont seulement 1 ou 2 à domicile, fréquent en tout début
      de saison où N≥5 par rôle est mathématiquement quasi impossible
      avant la 10e-12e journée). Aucune autre clé n'est présente dans
      ce cas, ne jamais lire "lambdas"/"marches" sans vérifier le
      statut d'abord. Note : l'insuffisance de la fenêtre GLOBALE seule
      ne bloque PAS le match (elle rend juste λ_global None pour
      l'équipe concernée, voir _stats_globales).
    - "OK" sinon, avec "fenetres" (diagnostic des fenêtres TOTALES
      utilisées pour le gate -- pas les sous-ensembles domicile/
      extérieur), "lambdas", "marches_par_scenario",
      "robustesse_par_marche".

    IMPORTANT, conséquence du correctif ci-dessus : une fois le total
    validé (N≥5), les moyennes GF/GA domicile (pour A) et extérieur
    (pour B) sont calculées avec le sous-ensemble domicile-seul/
    extérieur-seul DISPONIBLE dans les 12 matchs totaux les plus
    récents retenus -- SANS nouveau seuil N≥5 appliqué à ce
    sous-ensemble (décision explicite de Patrick : "on calcule les
    moyennes avec les données dont on dispose"). Si ce sous-ensemble
    est vide (ex. une équipe qui n'a joué qu'à l'extérieur jusqu'ici),
    la moyenne devient None proprement (distributions.moyenne sur liste
    vide, jamais un crash) et le scénario offensif/défensif concerné
    devient None via lambda_estimators, sans affecter les autres
    scénarios -- la robustesse (écart-type sur 4 valeurs dont une
    None) deviendra alors INDETERMINE pour ce marché, ce qui le fera
    rejeter par le filtre (ROBUSTESSE_INDISPONIBLE), sans jamais
    fabriquer une fausse confiance sur une moyenne à 1 match.
    """
    historique_domicile = loader.recupere_historique_saison_courante(url_domicile, nom_competition, nom_domicile)
    historique_exterieur = loader.recupere_historique_saison_courante(url_exterieur, nom_competition, nom_exterieur)

    fenetre_a = validation.classifie_fenetre(historique_domicile)
    fenetre_b = validation.classifie_fenetre(historique_exterieur)

    if fenetre_a["statut"] != validation.STATUT_UTILISABLE or fenetre_b["statut"] != validation.STATUT_UTILISABLE:
        return {"statut": "INSUFFISANT", "fenetres": {"A": fenetre_a, "B": fenetre_b}}

    matchs_dom_domicile, _ = loader.separe_domicile_exterieur(fenetre_a["matchs_retenus"])
    _, matchs_ext_exterieur = loader.separe_domicile_exterieur(fenetre_b["matchs_retenus"])

    stats_off_a = team_stats.stats_offensives(matchs_dom_domicile)
    stats_def_a = team_stats.stats_defensives(matchs_dom_domicile)
    stats_off_b = team_stats.stats_offensives(matchs_ext_exterieur)
    stats_def_b = team_stats.stats_defensives(matchs_ext_exterieur)

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


# ============================================================================
# ORCHESTRATION COMPLÈTE (chantier du 09/09/2026, reprise de session) --
# enchaîne analyse_match() ci-dessus avec h2h/signals/edv/odds_provider pour
# produire une vraie sélection P1/P2/P3 sur un match réel. Additif uniquement
# -- analyse_match() ci-dessus n'est pas modifiée.
#
# PÉRIMÈTRE v1, décision EXPLICITE pour ne pas élargir la portée du chantier
# sans le dire (règle de travail de Patrick) : couvre EXACTEMENT les 5
# marchés déjà robustesse-évalués par analyse_match() -- 1X2 (domicile/nul/
# extérieur), BTTS (oui/non), Over 2.5. Handicap/TeamGoals/Double Chance/
# combos restent HORS PÉRIMÈTRE tant que `robustesse_par_marche` n'est pas
# étendu à ces marchés (voir docstring d'analyse_match() ci-dessus,
# "périmètre assumé restant" -- extension directe, structure déjà générique,
# mais chantier séparé, pas fait ici).
#
# CONSÉQUENCE ASSUMÉE de ce périmètre restreint : seuls 2 groupes
# d'exposition existent en v1 (GROUPE_RESULTAT, GROUPE_BUTS) -- P3 exige un
# 3e groupe distinct de P1 et P2, donc P3 sera quasi toujours None tant que
# le périmètre n'est pas étendu. C'est une conséquence mécanique du périmètre
# choisi, pas un bug de selector.py (déjà testé unitairement par ailleurs).
# ============================================================================


def _par_scenario(marches_par_scenario, extracteur):
    """Comme _valeurs_4_scenarios ci-dessus, mais retourne un dict
    {scenario: valeur} plutôt qu'une liste ordonnée -- c'est le format
    attendu par signals.convergence.filtre_marche_convergent
    (nombre_matchs_par_scenario/probabilites_par_scenario)."""
    return {s: extracteur(marches_par_scenario[s]) for s in SCENARIOS}


def _construit_candidat(*, marche, market_family, exposure_group,
                         marches_par_scenario, extracteur, cote,
                         robustesse_statut, n_par_scenario,
                         h2h_palier, h2h_statut, signal):
    """
    Applique le filtre de convergence (unanimité des 4 scénarios) à UN
    marché. Retourne (candidat, diagnostic) -- `candidat` est None si le
    marché est rejeté (jamais transmis en aval à dedup/selector), le
    diagnostic est TOUJOURS renvoyé (marché éligible ou non) pour audit.

    `signal` : dict produit par signals.statistiques_signal (ou None si
    aucune fonction de signal n'existe pour ce marché précis -- ex. le nul
    en 1X2, voir docstring d'analyse_match_complet). Dans ce cas,
    signal_direction/signal_frequence restent None sur le candidat --
    dégradé proprement (selector.py traite déjà une valeur absente comme
    le rang le plus bas, jamais un crash, voir signals/selector.py).
    """
    probabilites = _par_scenario(marches_par_scenario, extracteur)
    resultat = convergence.filtre_marche_convergent(
        nombre_matchs_par_scenario=n_par_scenario,
        probabilites_par_scenario=probabilites,
        cote=cote,
        robustesse=robustesse_statut,
        marche=marche,
        market_family=market_family,
        exposure_group=exposure_group,
    )
    diagnostic = {"marche": marche, "filtre": resultat.as_dict(), "h2h_statut": h2h_statut}

    if not resultat.eligible:
        return None, diagnostic

    p_repr = probabilites[SCENARIO_REPRESENTATIF]
    valeur = edv_calculator.evalue_valeur(p_repr, cote)
    candidat = {
        "marche": marche,
        "market_family": market_family,
        "exposure_group": exposure_group,
        "niveau": resultat.resultats_par_scenario[SCENARIO_REPRESENTATIF].niveau,
        "robustesse": robustesse_statut,
        "edge": valeur["edge"],
        "edv": valeur["edv"],
        "h2h_palier": h2h_palier,
        "signal_direction": signal["direction"] if signal else None,
        "signal_frequence": signal["frequence"] if signal else None,
    }
    return candidat, diagnostic


def analyse_match_complet(url_domicile, nom_domicile, url_exterieur, nom_exterieur,
                           nom_competition, match_id, url_h2h=None,
                           chemin_precalcul="precalcul.json", cotes_info=None):
    """
    Orchestration complète d'un match réel A (domicile) contre B (extérieur) :
    data -> statistiques -> multi-λ -> Poisson -> H2H -> signal Statistiques
    -> cotes réelles -> Edge/EDV -> filtre (unanimité 4 scénarios) ->
    dédoublonnage -> sélection P1/P2/P3.

    Voir le commentaire de section ci-dessus pour le périmètre v1 (5
    marchés) et ses conséquences assumées.

    `url_h2h` : optionnel -- si absent (None), le H2H est traité comme
    INSUFFISANT (0 confrontation) plutôt que de lever une exception :
    l'absence de la page H2H ne doit jamais bloquer l'analyse des autres
    étapes (le H2H n'est de toute façon jamais décisionnel avant la
    sélection, voir l'audit d'intégration bout en bout de la séance
    précédente).

    `cotes_info` : optionnel -- dict au format retourné par
    `data.odds_provider.recupere_cotes_pour_match` (ou son équivalent
    `extrait_cotes` + `"statut": "OK"` ajouté par l'appelant). Si fourni,
    AUCUNE lecture de `chemin_precalcul` n'est faite -- utilisé par le
    branchement precalcul.py (chantier du 09/09/2026, reprise) pour passer
    les cotes DÉJÀ calculées EN MÉMOIRE par l'ancien moteur dans la même
    exécution, plutôt que de relire `precalcul.json` sur disque -- ce
    fichier est justement celui que ce même run est en train de
    construire, donc pas encore à jour pour CE match précis au moment de
    l'appel. Si None (comportement historique, inchangé, tests existants
    non affectés), lit `chemin_precalcul` comme avant.

    SIGNAL STATISTIQUES PAR MARCHÉ, convention V1 -- décision documentée
    ici, PAS donnée littéralement par le v3, à confirmer/ajuster si le v3
    en dit autrement :
    - 1X2 domicile   -> signal_victoire de l'équipe domicile (A)
    - 1X2 extérieur  -> signal_victoire de l'équipe extérieure (B)
    - 1X2 nul        -> aucune fonction de signal n'existe pour le nul
      dans statistiques_signal.py -- signal_direction/frequence restent
      None pour ce candidat (jamais une valeur inventée)
    - BTTS oui/non   -> signal_btts de l'équipe domicile (A)
    - Over 2.5       -> signal_over_under_total(2.5) de l'équipe domicile (A)

    Retourne un dict avec au moins la clé "statut" :
    - "INSUFFISANT" : fenêtre domicile ou extérieure insuffisante, propagé
      tel quel depuis analyse_match() (voir sa docstring) ;
    - "COTES_INDISPONIBLES" : match absent de `chemin_precalcul` (ou du
      `cotes_info` fourni), ou pipeline existant n'a pas encore traité ce
      match ;
    - "OK" : "candidats" (tous les marchés ÉLIGIBLES après filtre, avant
      dédoublonnage), "candidats_dedupliques", "selection"
      ({"P1":..., "P2":..., "P3":...}, chaque valeur pouvant être None),
      "diagnostics" (un par marché testé, y compris les rejetés, pour audit),
      "h2h" (palier + statut CORROBORE/CONTREDIT/NEUTRE/INSUFFISANT par
      marché -- affiché pour explication, jamais utilisé pour décider,
      voir l'audit d'intégration de la séance précédente), "cotes_info"
      (source_cotes/est_betpawa/marches_non_couverts, transparence sur
      l'origine des cotes).

    IMPORTANT pour l'appelant (voir precalcul.py, chantier du 09/09/2026) :
    "INSUFFISANT" et "COTES_INDISPONIBLES" sont des DÉCISIONS NORMALES de
    ce moteur, pas des pannes -- ne doivent JAMAIS déclencher un repli vers
    l'ancien moteur. Seule une EXCEPTION PYTHON non attrapée ici (réseau,
    parsing, bug) est une vraie erreur technique justifiant un fallback --
    décision explicite de Patrick (09/09/2026), à ne jamais contourner.
    """
    base = analyse_match(url_domicile, nom_domicile, url_exterieur, nom_exterieur, nom_competition)
    if base["statut"] != "OK":
        return {"statut": base["statut"], "fenetres": base.get("fenetres")}

    # --- H2H (dégradé proprement si pas d'URL fournie, jamais une exception) ---
    confrontations = h2h_stats.recupere_confrontations(url_h2h, nom_domicile) if url_h2h else []
    fenetre_h2h = h2h_stats.classifie_h2h(confrontations)

    # --- Cotes réelles (pipeline existant, voir data/odds_provider.py) ---
    if cotes_info is None:
        cotes_info = odds_provider.recupere_cotes_pour_match(match_id, chemin_precalcul)
    if cotes_info["statut"] != "OK":
        return {"statut": "COTES_INDISPONIBLES", "fenetres": base["fenetres"], "match_id": match_id}
    cotes = cotes_info["cotes"]

    marches_par_scenario = base["marches_par_scenario"]
    robustesse_par_marche = base["robustesse_par_marche"]
    # Même N pour les 4 scénarios (précédent déjà établi par l'audit
    # d'intégration bout en bout de la séance précédente, voir
    # audit_permanent.py section "AUDIT D'INTÉGRATION BOUT EN BOUT") --
    # pas une nouvelle convention inventée ici.
    n_par_scenario = {s: len(base["fenetres"]["A"]["matchs_retenus"]) for s in SCENARIOS}

    m_repr = marches_par_scenario[SCENARIO_REPRESENTATIF]
    p_1x2_repr = m_repr["1x2"]
    statut_h2h_1x2 = h2h_markets.evalue_1x2(fenetre_h2h, p_1x2_repr) if p_1x2_repr else h2h_markets.STATUT_INSUFFISANT
    p_btts_repr = m_repr["btts"]
    statut_h2h_btts = h2h_markets.evalue_btts(fenetre_h2h, p_btts_repr) if p_btts_repr is not None else h2h_markets.STATUT_INSUFFISANT
    p_over25_repr = m_repr["over_under_total"][2.5]["over"] if m_repr["over_under_total"][2.5] else None
    statut_h2h_over25 = h2h_markets.evalue_over_under_total(fenetre_h2h, 2.5, p_over25_repr) if p_over25_repr is not None else h2h_markets.STATUT_INSUFFISANT

    signal_victoire_a = statistiques_signal.signal_victoire(base["fenetres"]["A"])
    signal_victoire_b = statistiques_signal.signal_victoire(base["fenetres"]["B"])
    signal_btts_a = statistiques_signal.signal_btts(base["fenetres"]["A"])
    signal_over25_a = statistiques_signal.signal_over_under_total(base["fenetres"]["A"], 2.5)

    candidats = []
    diagnostics = []

    def _ajoute(marche, family, group, extracteur, cle_cote, robustesse_key, signal, h2h_statut):
        candidat, diag = _construit_candidat(
            marche=marche, market_family=family, exposure_group=group,
            marches_par_scenario=marches_par_scenario, extracteur=extracteur,
            cote=cotes.get(cle_cote),
            robustesse_statut=robustesse_par_marche[robustesse_key]["statut"],
            n_par_scenario=n_par_scenario, h2h_palier=fenetre_h2h["palier"],
            h2h_statut=h2h_statut, signal=signal,
        )
        diagnostics.append(diag)
        if candidat is not None:
            candidats.append(candidat)

    _ajoute("1x2_domicile", "RESULT", "GROUPE_RESULTAT",
            lambda m: m["1x2"]["domicile"] if m["1x2"] else None,
            ("1x2", "domicile"), "1x2_domicile", signal_victoire_a, statut_h2h_1x2)
    _ajoute("1x2_nul", "RESULT", "GROUPE_RESULTAT",
            lambda m: m["1x2"]["nul"] if m["1x2"] else None,
            ("1x2", "nul"), "1x2_nul", None, statut_h2h_1x2)
    _ajoute("1x2_exterieur", "RESULT", "GROUPE_RESULTAT",
            lambda m: m["1x2"]["exterieur"] if m["1x2"] else None,
            ("1x2", "exterieur"), "1x2_exterieur", signal_victoire_b, statut_h2h_1x2)
    _ajoute("btts_oui", "BTTS", "GROUPE_BUTS",
            lambda m: m["btts"],
            ("btts", "oui"), "btts", signal_btts_a, statut_h2h_btts)
    _ajoute("btts_non", "BTTS", "GROUPE_BUTS",
            lambda m: (1.0 - m["btts"]) if m["btts"] is not None else None,
            ("btts", "non"), "btts", signal_btts_a, statut_h2h_btts)
    _ajoute("over_2.5", "GOALS_TOTAL", "GROUPE_BUTS",
            lambda m: m["over_under_total"][2.5]["over"] if m["over_under_total"][2.5] else None,
            ("over_under_total", 2.5, "over"), "over_2_5", signal_over25_a, statut_h2h_over25)

    candidats_dedupliques = deduplication.deduplique(candidats, critere="edge") if candidats else []
    selection = selector.selectionner(candidats_dedupliques)

    return {
        "statut": "OK",
        "fenetres": base["fenetres"],
        "lambdas": base["lambdas"],
        "candidats": candidats,
        "candidats_dedupliques": candidats_dedupliques,
        "selection": selection,
        "diagnostics": diagnostics,
        "h2h": {
            "palier": fenetre_h2h["palier"],
            "1x2": statut_h2h_1x2,
            "btts": statut_h2h_btts,
            "over_2.5": statut_h2h_over25,
        },
        "cotes_info": {k: v for k, v in cotes_info.items() if k != "cotes"},
    }
