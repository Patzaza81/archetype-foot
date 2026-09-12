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
from .poisson import distribution
from .poisson import robustness
from .h2h import h2h_stats
from .h2h import h2h_markets
from .signals import statistiques_signal
from .signals import convergence
from .signals import deduplication
from .signals import selector
import justification
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
        # Historique complet conservé uniquement en mémoire pour construire
        # les preuves d'affichage après sélection. Il n'entre dans aucun
        # calcul du modèle et est retiré avant la sortie finale.
        "_historique_justification": {"A": historique_domicile, "B": historique_exterieur},
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
                         h2h_palier, h2h_statut, signal,
                         matchs_a_domicile=None, matchs_b_exterieur=None,
                         historique_a=None, historique_b=None,
                         confrontations_h2h=None, nom_domicile="", nom_exterieur=""):

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

    `matchs_a_domicile`/`matchs_b_exterieur` (10/09/2026, demande de
    Patrick) : les matchs RÉELS déjà chargés (fenetres.A/B.matchs_retenus),
    passés à justification.confirmation_historique() pour produire un
    comptage PUREMENT DESCRIPTIF ("7 des 8 derniers matchs..."), ajouté au
    candidat une fois la décision déjà prise -- n'entre dans aucun calcul
    de probabilité, de filtre ou de sélection ci-dessus.
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
        "probabilite": p_repr,
        "cote": cote,
        "edge": valeur["edge"],
        "edv": valeur["edv"],
        "h2h_palier": h2h_palier,
        "signal_direction": signal["direction"] if signal else None,
        "signal_frequence": signal["frequence"] if signal else None,
        "confirmation_historique": justification.confirmation_historique(
            marche, matchs_a_domicile, matchs_b_exterieur
        ) if matchs_a_domicile is not None or matchs_b_exterieur is not None else None,
        "justification": justification.construit_justification(
            marche, historique_a or [], historique_b or [],
            h2h=confrontations_h2h or [],
            nom_domicile=nom_domicile, nom_exterieur=nom_exterieur,
        ),
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
    # Chantier du 09/09/2026 : même signal (buts de B à la ligne 0.5) pour
    # cage_inviolee_domicile ET encaisse_domicile -- ce sont les deux faces
    # de la même statistique (buts encaissés par B, vu du signal de B).
    signal_buts_b_05 = statistiques_signal.signal_buts_equipe(base["fenetres"]["B"], 0.5)
    signal_buts_a_05 = statistiques_signal.signal_buts_equipe(base["fenetres"]["A"], 0.5)

    candidats = []
    diagnostics = []

    # Filtrage par rôle une seule fois (pas à chaque marché) -- réutilisé
    # par tous les appels _ajoute() et par la boucle dynamique plus bas.
    # A joue à domicile aujourd'hui -> ses matchs À DOMICILE passés ; B
    # joue à l'extérieur aujourd'hui -> ses matchs À L'EXTÉRIEUR passés.
    # Même convention que lambda_estimators.py (gf_a_domicile, ga_b_exterieur).
    _matchs_a_domicile = [m for m in base["fenetres"]["A"]["matchs_retenus"] if m.get("domicile") is True]
    _matchs_b_exterieur = [m for m in base["fenetres"]["B"]["matchs_retenus"] if m.get("domicile") is False]
    _historique_a_justif = base.get("_historique_justification", {}).get("A", [])
    _historique_b_justif = base.get("_historique_justification", {}).get("B", [])
    _h2h_justif = fenetre_h2h.get("confrontations_retenues", [])

    def _ajoute(marche, family, group, extracteur, cle_cote, robustesse_key, signal, h2h_statut):
        candidat, diag = _construit_candidat(
            marche=marche, market_family=family, exposure_group=group,
            marches_par_scenario=marches_par_scenario, extracteur=extracteur,
            cote=cotes.get(cle_cote),
            robustesse_statut=robustesse_par_marche[robustesse_key]["statut"],
            n_par_scenario=n_par_scenario, h2h_palier=fenetre_h2h["palier"],
            h2h_statut=h2h_statut, signal=signal,
            matchs_a_domicile=_matchs_a_domicile, matchs_b_exterieur=_matchs_b_exterieur,
            historique_a=_historique_a_justif, historique_b=_historique_b_justif,
            confrontations_h2h=_h2h_justif,
            nom_domicile=nom_domicile, nom_exterieur=nom_exterieur,
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

    # Chantier du 09/09/2026 (feu vert de Patrick) -- extension du périmètre
    # v1 à 4 marchés de plus, tous deux déjà calculables avec les cotes déjà
    # récupérées (voir data/odds_provider.py) :
    _ajoute("cage_inviolee_domicile", "CLEAN_SHEET_DOMICILE", "GROUPE_BUTS",
            lambda m: m["buts_equipe_exterieur"][0.5]["under"] if m["buts_equipe_exterieur"][0.5] else None,
            ("buts_equipe_exterieur", 0.5, "under"), "cage_inviolee_domicile",
            signal_buts_b_05, None)
    _ajoute("encaisse_domicile", "CLEAN_SHEET_DOMICILE", "GROUPE_BUTS",
            lambda m: m["buts_equipe_exterieur"][0.5]["over"] if m["buts_equipe_exterieur"][0.5] else None,
            ("buts_equipe_exterieur", 0.5, "over"), "cage_inviolee_domicile",
            signal_buts_b_05, None)
    _ajoute("cage_inviolee_exterieur", "CLEAN_SHEET_EXTERIEUR", "GROUPE_BUTS",
            lambda m: m["buts_equipe_domicile"][0.5]["under"] if m["buts_equipe_domicile"][0.5] else None,
            ("buts_equipe_domicile", 0.5, "under"), "cage_inviolee_exterieur",
            signal_buts_a_05, None)
    _ajoute("encaisse_exterieur", "CLEAN_SHEET_EXTERIEUR", "GROUPE_BUTS",
            lambda m: m["buts_equipe_domicile"][0.5]["over"] if m["buts_equipe_domicile"][0.5] else None,
            ("buts_equipe_domicile", 0.5, "over"), "cage_inviolee_exterieur",
            signal_buts_a_05, None)
    _ajoute("parite_pair", "PARITE", "GROUPE_BUTS",
            lambda m: m["parite_totale"]["pair"] if m["parite_totale"] else None,
            ("parite_totale", "pair"), "parite_pair", None, None)
    _ajoute("parite_impair", "PARITE", "GROUPE_BUTS",
            lambda m: m["parite_totale"]["impair"] if m["parite_totale"] else None,
            ("parite_totale", "impair"), "parite_pair", None, None)

    # ========================================================================
    # CHANTIER DU 10/09/2026 (feu vert de Patrick) -- PÉRIMÈTRE DYNAMIQUE,
    # piloté par les cotes réellement disponibles plutôt que par une liste
    # figée. Les 12 `_ajoute()` ci-dessus restent INCHANGÉS (mêmes clés
    # `market_family`/`exposure_group`, même comportement, zéro régression
    # possible sur les candidats déjà en production). Ce bloc ajoute
    # uniquement les clés de `cotes` qui ne sont PAS déjà couvertes par les
    # 12 appels fixes : Double Chance, Over/Under sur toute ligne réellement
    # cotée, Handicap sur toute ligne réellement cotée, buts par équipe sur
    # les lignes autres que 0.5 (déjà prises par cage_inviolee/encaisse).
    #
    # PAS INCLUS ici, volontairement (chantier séparé, pas de feu vert
    # encore donné) : les marchés combinés DC+Total (poisson/markets.py::
    # probabilite_combo_dc_total). Ils partagent une exposition économique
    # avec leurs marchés composants (ex. combo "1X + Over 2.5" est corrélé
    # à la fois avec Double Chance 1X ET avec Over 2.5) -- deduplication.py
    # ne dédouble que par (famille, groupe) simple, pas par recouvrement
    # entre plusieurs groupes à la fois. Les ajouter sans y réfléchir
    # d'abord romprait silencieusement l'invariant anti-corrélation posé le
    # 09/09/2026.
    #
    # Contrairement aux 12 marchés fixes (qui utilisent `marches_par_scenario`,
    # déjà agrégé sur les lignes PAR DÉFAUT de poisson/markets.py), ce bloc
    # recalcule matrice/distribution directement depuis les lambdas déjà
    # obtenus -- calcul pur, aucun fetch réseau supplémentaire -- pour
    # couvrir n'importe quelle ligne réellement cotée, y compris celles hors
    # des lignes par défaut (ex. Over/Under 5.5/6.5/7.5, Handicap +-2.5).
    #
    # EXPOSURE_GROUP -- décision explicite à valider avec Patrick avant
    # bascule en production :
    #   - Double Chance partage GROUPE_RESULTAT avec 1X2 (corrélation
    #     directe : DC 1X et 1X2 domicile parient tous les deux sur "le
    #     domicile ne perd pas"), mais une AUTRE famille ("DOUBLE_CHANCE"
    #     vs "RESULT") -- dedup ne gardera donc qu'UN SEUL candidat parmi
    #     TOUT GROUPE_RESULTAT (1X2 + DC confondus), jamais les deux à la
    #     fois sur le même match.
    #   - Handicap reçoit un troisième groupe, GROUPE_HANDICAP (nouveau,
    #     n'existait pas avant) -- distinct de GROUPE_RESULTAT et
    #     GROUPE_BUTS. Conséquence positive assumée : P3 (qui exige un 3e
    #     groupe distinct de P1 et P2) peut désormais réellement se
    #     déclencher, ce qui n'était quasi jamais possible avant (2 groupes
    #     seulement en périmètre v1, voir commentaire plus haut).
    #   - Over/Under (toutes lignes) et buts par équipe (lignes hors 0.5)
    #     restent dans GROUPE_BUTS, comme Over 2.5/BTTS/Parité déjà en
    #     place -- une ligne 1.5 et une ligne 3.5 sur le même total sont
    #     fortement corrélées, dedup doit les traiter comme concurrentes,
    #     pas comme deux paris indépendants.
    # ========================================================================
    lambdas_dyn = base["lambdas"]
    matrices_par_scenario = {
        s: distribution.matrice_scores(lambdas_dyn["A"][s], lambdas_dyn["B"][s]) for s in SCENARIOS
    }
    dist_a_par_scenario = {s: distribution.distribution_marginale(lambdas_dyn["A"][s]) for s in SCENARIOS}
    dist_b_par_scenario = {s: distribution.distribution_marginale(lambdas_dyn["B"][s]) for s in SCENARIOS}

    def _extractor_dynamique(cle):
        """Construit un extracteur (scenario -> probabilité) à partir d'une
        clé structurée d'odds_provider._parse_libelle. Retourne None si la
        clé n'est pas (encore) gérable dynamiquement (ex. combos, exclus
        volontairement ci-dessus)."""
        if cle[0] == "1x2":
            _, sel = cle
            return lambda s: markets.probabilites_1x2(matrices_par_scenario[s])[sel] if matrices_par_scenario[s] else None
        if cle[0] == "double_chance":
            _, sel = cle
            return lambda s: markets.probabilites_double_chance(matrices_par_scenario[s])[sel] if matrices_par_scenario[s] else None
        if cle[0] == "btts":
            _, sel = cle
            def _f(s):
                p = markets.probabilite_btts(matrices_par_scenario[s]) if matrices_par_scenario[s] else None
                return p if sel == "oui" else (1.0 - p if p is not None else None)
            return _f
        if cle[0] == "parite_totale":
            _, sel = cle
            return lambda s: markets.probabilite_parite_totale(matrices_par_scenario[s])[sel] if matrices_par_scenario[s] else None
        if cle[0] == "over_under_total":
            _, ligne, sens = cle
            def _f(s):
                p = markets.probabilites_over_under_total(matrices_par_scenario[s], ligne) if matrices_par_scenario[s] else None
                return p[sens] if p else None
            return _f
        if cle[0] == "buts_equipe_domicile":
            _, ligne, sens = cle
            def _f(s):
                p = markets.probabilites_buts_equipe(dist_a_par_scenario[s], ligne) if dist_a_par_scenario[s] else None
                return p[sens] if p else None
            return _f
        if cle[0] == "buts_equipe_exterieur":
            _, ligne, sens = cle
            def _f(s):
                p = markets.probabilites_buts_equipe(dist_b_par_scenario[s], ligne) if dist_b_par_scenario[s] else None
                return p[sens] if p else None
            return _f
        if cle[0] == "handicap":
            _, ligne, sel = cle
            def _f(s):
                r = markets.resultat_handicap(matrices_par_scenario[s], ligne) if matrices_par_scenario[s] else None
                if r is None:
                    return None
                return r["gain"] if sel == "domicile" else r["perte"]
            return _f
        if cle[0] == "combo_dc_total":
            _, dc, sens, ligne = cle
            return lambda s: markets.probabilite_combo_dc_total(matrices_par_scenario[s], dc, ligne, sens) if matrices_par_scenario[s] else None
        return None  # toute future extension non gérée -> ignoré, jamais un crash

    _CLES_DEJA_CABLEES = {
        ("1x2", "domicile"), ("1x2", "nul"), ("1x2", "exterieur"),
        ("btts", "oui"), ("btts", "non"),
        ("over_under_total", 2.5, "over"),
        ("buts_equipe_exterieur", 0.5, "under"), ("buts_equipe_exterieur", 0.5, "over"),
        ("buts_equipe_domicile", 0.5, "under"), ("buts_equipe_domicile", 0.5, "over"),
        ("parite_totale", "pair"), ("parite_totale", "impair"),
    }

    _FAMILLE_GROUPE = {
        "1x2": ("RESULT", "GROUPE_RESULTAT"),
        "double_chance": ("DOUBLE_CHANCE", "GROUPE_RESULTAT"),
        "over_under_total": ("GOALS_TOTAL", "GROUPE_BUTS"),
        "buts_equipe_domicile": ("GOALS_EQUIPE_DOMICILE", "GROUPE_BUTS"),
        "buts_equipe_exterieur": ("GOALS_EQUIPE_EXTERIEUR", "GROUPE_BUTS"),
        "handicap": ("HANDICAP", "GROUPE_HANDICAP"),
        # COMBO_DC_TOTAL (chantier demandé par Patrick le 10/09/2026) :
        # probabilité calculée CONJOINTEMENT (poisson.markets.probabilite_
        # combo_dc_total, jamais un produit naïf DC x Total -- les deux
        # dépendent du même score, v3 §9.4.3/9.4.4). Le calcul lui-même est
        # donc correct et testé. Le risque n'est pas dans le calcul de
        # probabilité mais dans la SÉLECTION : parier à la fois sur "1X" et
        # sur "1X + Over 1.5" pour le même match double l'exposition au même
        # évènement. Un simple exposure_group commun ne suffit pas ici (le
        # combo est corrélé à DEUX marchés différents à la fois, DC et
        # Total, pas à un seul groupe) -- voir le garde-fou explicite juste
        # après la boucle, qui retire un combo si son composant DC ou son
        # composant Total est déjà éligible sur ce match.
        "combo_dc_total": ("COMBO_DC_TOTAL", "GROUPE_COMBO_DC_TOTAL"),
    }

    def _nom_marche_dynamique(cle):
        if cle[0] in ("1x2", "double_chance"):
            return f"{cle[0]}_{cle[1]}"
        if cle[0] == "handicap":
            _, ligne, sel = cle
            return f"handicap_{sel}_{ligne}"
        if cle[0] == "combo_dc_total":
            _, dc, sens, ligne = cle
            return f"combo_{dc}_{sens}_{ligne}"
        _, ligne, sens = cle
        return f"{cle[0]}_{ligne}_{sens}"

    for cle_cote, cote_reelle in cotes.items():
        if cle_cote in _CLES_DEJA_CABLEES:
            continue
        if cle_cote[0] not in _FAMILLE_GROUPE:
            continue  # clé future non reconnue par ce module : ignorée, pas d'erreur
        extracteur_dyn = _extractor_dynamique(cle_cote)
        if extracteur_dyn is None:
            continue

        probabilites_dyn = {s: extracteur_dyn(s) for s in SCENARIOS}
        robustesse_dyn = robustness.evalue_robustesse([probabilites_dyn[s] for s in SCENARIOS])
        robustesse_statut_dyn = robustesse_dyn["statut"] if isinstance(robustesse_dyn, dict) else robustesse_dyn

        marche_nom = _nom_marche_dynamique(cle_cote)
        family, group = _FAMILLE_GROUPE[cle_cote[0]]

        resultat_dyn = convergence.filtre_marche_convergent(
            nombre_matchs_par_scenario=n_par_scenario,
            probabilites_par_scenario=probabilites_dyn,
            cote=cote_reelle,
            robustesse=robustesse_statut_dyn,
            marche=marche_nom,
            market_family=family,
            exposure_group=group,
        )
        diagnostics.append({"marche": marche_nom, "filtre": resultat_dyn.as_dict(), "h2h_statut": None})

        if resultat_dyn.eligible:
            p_repr_dyn = probabilites_dyn[SCENARIO_REPRESENTATIF]
            valeur_dyn = edv_calculator.evalue_valeur(p_repr_dyn, cote_reelle)
            candidats.append({
                "marche": marche_nom,
                "market_family": family,
                "exposure_group": group,
                "niveau": resultat_dyn.resultats_par_scenario[SCENARIO_REPRESENTATIF].niveau,
                "robustesse": robustesse_statut_dyn,
                "probabilite": p_repr_dyn,
                "cote": cote_reelle,
                "edge": valeur_dyn["edge"],
                "edv": valeur_dyn["edv"],
                "h2h_palier": fenetre_h2h["palier"],
                "signal_direction": None,
                "signal_frequence": None,
                "confirmation_historique": justification.confirmation_historique(
                    marche_nom, _matchs_a_domicile, _matchs_b_exterieur
                ),
                "justification": justification.construit_justification(
                    marche_nom, _historique_a_justif, _historique_b_justif,
                    h2h=_h2h_justif, nom_domicile=nom_domicile, nom_exterieur=nom_exterieur,
                ),
                "_cle_cote": cle_cote,  # interne, retiré avant retour -- clé structurée
                                        # d'origine, nécessaire au garde-fou anti-corrélation
                                        # combo ci-dessous (jamais du texte reparsé).
            })

    # GARDE-FOU ANTI-CORRÉLATION COMBO (chantier du 10/09/2026, demandé par
    # Patrick) : un candidat combo_dc_total est retiré si son composant DC
    # (même sélection 1X/X2/12) OU son composant Total (même ligne ET même
    # sens) est LUI-MÊME éligible sur ce match -- sinon un pari et sa
    # variante combinée pourraient être sélectionnés tous les deux, ce qui
    # double l'exposition au même évènement. Comparaison sur les clés
    # STRUCTURÉES (`_cle_cote`), jamais sur le texte du nom de marché.
    _dc_eligibles = {c["_cle_cote"][1] for c in candidats if c.get("_cle_cote", (None,))[0] == "double_chance"}
    _total_eligibles = {
        (c["_cle_cote"][1], c["_cle_cote"][2]) for c in candidats
        if c.get("_cle_cote", (None,))[0] == "over_under_total"
    }

    def _combo_est_correle(cle):
        _, dc, sens, ligne = cle
        return dc in _dc_eligibles or (ligne, sens) in _total_eligibles

    candidats = [
        c for c in candidats
        if c.get("_cle_cote", (None,))[0] != "combo_dc_total" or not _combo_est_correle(c["_cle_cote"])
    ]
    for c in candidats:
        c.pop("_cle_cote", None)

    candidats_dedupliques = deduplication.deduplique(candidats, critere="edge") if candidats else []
    selection = selector.selectionner(candidats_dedupliques)

    # AJOUT 12/09/2026 (demande de Patrick : "la vraie raison du choix") --
    # PUREMENT APRÈS COUP : P1/P2/P3 sont déjà figés par la ligne
    # ci-dessus, rien ici ne les relit pour décider quoi que ce soit.
    # diagnostique_selection() ne fait que comparer, après coup, le
    # candidat retenu à son meilleur concurrent resté sur le carreau, pour
    # que la justification affichée dise la vraie raison de la sélection
    # au lieu d'une phrase reconstituée depuis l'historique seul.
    diagnostic_selection = selector.diagnostique_selection(candidats_dedupliques, selection)
    for _rang in ("P1", "P2", "P3"):
        justification.enrichit_justification_selection(
            selection.get(_rang), diagnostic_selection.get(_rang)
        )

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
