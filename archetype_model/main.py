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

PÉRIMÈTRE MARCHÉS : le moteur calcule les familles couvertes par
`poisson.markets`, puis `analyse_match_complet()` utilise le registre
dynamique des marchés réellement cotés. La robustesse des marchés dynamiques
est calculée au moment de leur évaluation ; aucune famille cotée n’est
écartée uniquement parce qu’elle n’était pas dans l’ancienne liste de 12.

`backtest.boucle_b` calcule maintenant λ_global de la même façon
  (compétition unique, domicile+extérieur fusionnés) -- possible sans
  fetch supplémentaire car `cache_equipes.json` contient déjà les deux
  listes par équipe pour cette compétition.
"""

import os
import statistics

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
from .signals import market_registry
from .edv import calculator as edv_calculator
import justification

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

# Mode de décision : le mode historique 4/4 reste disponible pour comparaison.
# Le mode 3/4 reste explicitement optionnel pour les études comparatives.
# La production reste par défaut en unanimité 4/4.
MODE_CONVERGENCE = os.getenv("ARCHETYPE_MODE_CONVERGENCE", "UNANIMITE_4_4").strip().upper()
if MODE_CONVERGENCE not in {"UNANIMITE_4_4", "CONSENSUS_3_4"}:
    MODE_CONVERGENCE = "UNANIMITE_4_4"


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
        # Chantier du 09/09/2026 (feu vert de Patrick) : cage_inviolee_domicile
        # réutilise buts_equipe_exterieur[0.5] -- même robustesse sert aux deux
        # candidats complémentaires (cage inviolée ET encaisse au moins 1 but),
        # exactement comme "btts" sert à la fois btts_oui et btts_non.
        "cage_inviolee_domicile": robustness.evalue_robustesse(
            _valeurs_4_scenarios(marches_par_scenario, lambda m: m["buts_equipe_exterieur"][0.5]["under"] if m["buts_equipe_exterieur"][0.5] else None)),
        "cage_inviolee_exterieur": robustness.evalue_robustesse(
            _valeurs_4_scenarios(marches_par_scenario, lambda m: m["buts_equipe_domicile"][0.5]["under"] if m["buts_equipe_domicile"][0.5] else None)),
        "parite_pair": robustness.evalue_robustesse(
            _valeurs_4_scenarios(marches_par_scenario, lambda m: m["parite_totale"]["pair"] if m["parite_totale"] else None)),
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
# PÉRIMÈTRE v2 (09/09/2026, feu vert de Patrick, complété en 2e passe --
# "tout ajouter sans exception si les données permettent de calculer sans
# ambiguïté") : couvre les 5 marchés déjà robustesse-évalués par
# analyse_match() en v1 -- 1X2 (domicile/nul/extérieur), BTTS (oui/non),
# Over 2.5 -- PLUS 4 marchés ajoutés ce jour, domicile ET extérieur :
# Cage inviolée / Encaisse au moins 1 but (réutilisent buts_equipe_domicile/
# buts_equipe_exterieur[0.5] déjà calculés), et Parité totale (pair/impair,
# nouvelle fonction poisson/markets.py::probabilite_parite_totale). Soit
# 12 candidats au total. Handicap/TeamGoals/Double Chance/combos restent
# HORS PÉRIMÈTRE tant que `robustesse_par_marche` n'est pas étendu à ces
# marchés -- chantier séparé, pas fait ici.
#
# CONSÉQUENCE ASSUMÉE de ce périmètre : les 12 candidats ne couvrent
# toujours que 2 groupes d'exposition (GROUPE_RESULTAT, GROUPE_BUTS) --
# les 9 hors 1X2 partagent tous GROUPE_BUTS. P3 exige un 3e groupe
# distinct de P1 et P2, donc P3 reste quasi toujours None tant que le
# périmètre n'est pas étendu à un 3e groupe (ex. Handicap). C'est une
# conséquence mécanique du périmètre choisi, pas un bug de selector.py
# (déjà testé unitairement par ailleurs).
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
    filtre_convergence = (
        convergence.filtre_marche_consensus_3_sur_4
        if MODE_CONVERGENCE == "CONSENSUS_3_4"
        else convergence.filtre_marche_convergent
    )
    resultat = filtre_convergence(
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

    # En consensus 3/4, aucune branche n'est privilégiée : la médiane des
    # quatre probabilités constitue la valeur centrale affichée et économique.
    # En mode historique 4/4, on conserve strictement la convention offensive.
    probabilites_valides = [
        float(p) for p in probabilites.values()
        if isinstance(p, (int, float)) and not isinstance(p, bool) and 0.0 <= float(p) <= 1.0
    ]
    if MODE_CONVERGENCE == "CONSENSUS_3_4" and probabilites_valides:
        p_repr = statistics.median(probabilites_valides)
        valeur = edv_calculator.evalue_valeur(p_repr, cote)
        niveau_repr = convergence.filtre_marche(
            nombre_matchs=n_par_scenario.get(SCENARIOS[0]),
            probabilite_centrale=p_repr,
            cote=cote,
            edv=valeur["edv"],
            robustesse=robustesse_statut,
            marche=marche, market_family=market_family, exposure_group=exposure_group,
        ).niveau
    else:
        p_repr = probabilites[SCENARIO_REPRESENTATIF]
        valeur = edv_calculator.evalue_valeur(p_repr, cote)
        niveau_repr = resultat.resultats_par_scenario[SCENARIO_REPRESENTATIF].niveau
    candidat = {
        "marche": marche,
        "market_family": market_family,
        "exposure_group": exposure_group,
        "niveau": niveau_repr,
        "probabilite_centrale": p_repr,
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
    -> cotes réelles -> Edge/EDV -> filtre (mode de convergence actif) ->
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
    # Chantier du 09/09/2026 : même signal (buts de B à la ligne 0.5) pour
    # cage_inviolee_domicile ET encaisse_domicile -- ce sont les deux faces
    # de la même statistique (buts encaissés par B, vu du signal de B).
    signal_buts_b_05 = statistiques_signal.signal_buts_equipe(base["fenetres"]["B"], 0.5)
    signal_buts_a_05 = statistiques_signal.signal_buts_equipe(base["fenetres"]["A"], 0.5)

    # ------------------------------------------------------------------
    # PÉRIMÈTRE DYNAMIQUE DES MARCHÉS
    # ------------------------------------------------------------------
    # Avant ce chantier, le moteur possédait 12 candidats codés en dur
    # alors que precalcul.json expose déjà plusieurs dizaines de marchés
    # réellement cotés et que poisson.markets sait les calculer.
    # Le périmètre économique devient donc piloté par les cotes observées,
    # sans inventer de nouveau seuil de sélection.
    registre_marches = market_registry.depuis_cotes(cotes)
    lignes_total = [k[1] for k in cotes if isinstance(k, tuple) and k and k[0] == "over_under_total"]
    lignes_team = [k[1] for k in cotes if isinstance(k, tuple) and k and k[0] in ("buts_equipe_domicile", "buts_equipe_exterieur")]
    lignes_handicap = [k[1] for k in cotes if isinstance(k, tuple) and k and k[0] == "handicap"]
    if lignes_total or lignes_team or lignes_handicap:
        marches_par_scenario = {
            scenario: markets.calcule_tous_les_marches(
                base["lambdas"]["A"][scenario],
                base["lambdas"]["B"][scenario],
                lignes_total=lignes_total or None,
                lignes_buts_equipe=lignes_team or None,
                lignes_handicap=lignes_handicap or None,
            )
            for scenario in SCENARIOS
        }

    candidats = []
    diagnostics = []

    # UNE SEULE source de vérité pour le périmètre de marchés : les cotes
    # réellement observées. Chaque marché reconnu passe par exactement le
    # même moteur de décision (4 scénarios, stabilité, cote, probabilité,
    # EDV). Aucun marché n'est oublié parce qu'il n'était pas dans une liste
    # historique codée en dur.
    for definition in registre_marches:
        probabilites = _par_scenario(marches_par_scenario, definition.extracteur)
        robustesse_dynamique = robustness.evalue_robustesse(list(probabilites.values()))

        # Les signaux/H2H spécifiques restent des informations auxiliaires,
        # jamais des règles de sélection supplémentaires. Ils sont utilisés
        # seulement pour les familles historiques où ils existent déjà.
        signal = None
        h2h_statut = None
        if definition.cle[0] == "1x2":
            signal = signal_victoire_a if definition.cle[1] == "domicile" else signal_victoire_b if definition.cle[1] == "exterieur" else None
            h2h_statut = statut_h2h_1x2
        elif definition.cle[0] == "btts":
            signal = signal_btts_a
            h2h_statut = statut_h2h_btts
        elif definition.cle == ("over_under_total", 2.5, "over"):
            signal = signal_over25_a
            h2h_statut = statut_h2h_over25
        elif definition.cle == ("buts_equipe_exterieur", 0.5, "under"):
            signal = signal_buts_b_05
        elif definition.cle == ("buts_equipe_exterieur", 0.5, "over"):
            signal = signal_buts_b_05
        elif definition.cle == ("buts_equipe_domicile", 0.5, "under"):
            signal = signal_buts_a_05
        elif definition.cle == ("buts_equipe_domicile", 0.5, "over"):
            signal = signal_buts_a_05

        candidat, diagnostic = _construit_candidat(
            marche=definition.nom,
            market_family=definition.famille,
            exposure_group=definition.exposition,
            marches_par_scenario=marches_par_scenario,
            extracteur=definition.extracteur,
            cote=cotes.get(definition.cle),
            robustesse_statut=robustesse_dynamique["statut"],
            n_par_scenario=n_par_scenario,
            h2h_palier=fenetre_h2h["palier"],
            h2h_statut=h2h_statut,
            signal=signal,
        )
        diagnostics.append(diagnostic)
        if candidat is not None:
            candidats.append(candidat)

    candidats_dedupliques = deduplication.deduplique(candidats, critere="edge") if candidats else []
    selection = selector.selectionner(candidats_dedupliques)

    # EXPLICATION POST-DÉCISION : cette étape est strictement descriptive.
    # Le sélecteur a déjà terminé P1/P2/P3 ; la justification ne peut ni
    # changer le marché, ni recalculer une probabilité, ni filtrer un candidat.
    resultat = {
        "statut": "OK",
        "mode_convergence": MODE_CONVERGENCE,
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
        "h2h_confrontations": fenetre_h2h["confrontations_retenues"],
    }

    return justification.enrichit_selection(
        resultat, nom_domicile=nom_domicile, nom_exterieur=nom_exterieur,
        h2h=fenetre_h2h["confrontations_retenues"]
    )
