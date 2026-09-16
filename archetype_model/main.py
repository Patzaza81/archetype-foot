"""
archetype_model/main.py — orchestration principale du modèle.
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
from .signals import selection_edv_directe
import justification
from .edv import calculator as edv_calculator

SCENARIOS = ("offensif", "defensif", "contextuel", "global")
SCENARIO_REPRESENTATIF = "offensif"


def _condition_pour_cle(cle_cote):
    """Fonction (buts_domicile, buts_exterieur) -> bool pour un marché
    donné, IDENTIQUE aux conditions déjà utilisées dans
    poisson/markets.py (jamais réinventées) -- nécessaire pour
    signals.selection_edv_directe (corrélation de Pearson exacte entre
    marchés du même match, AJOUT 16/09/2026).

    None si le type de marché n'a pas de condition simple sur un
    scoreline unique (handicap sur ligne au quart de but -- réparti
    50/50 sur deux lignes adjacentes, pas une indicatrice pure ; aucune
    ligne par défaut du projet n'est actuellement une ligne au quart,
    voir poisson/markets.py::resultat_handicap, donc ce cas ne se
    présente pas avec LIGNES_HANDICAP_PAR_DEFAUT, mais reste géré
    explicitement plutôt que de deviner une approximation fausse)."""
    type_marche = cle_cote[0]
    if type_marche == "1x2":
        sel = cle_cote[1]
        if sel == "domicile": return lambda x, y: x > y
        if sel == "nul": return lambda x, y: x == y
        return lambda x, y: x < y
    if type_marche == "double_chance":
        sel = cle_cote[1]
        if sel == "1X": return lambda x, y: x >= y
        if sel == "X2": return lambda x, y: x <= y
        return lambda x, y: x != y
    if type_marche == "btts":
        sel = cle_cote[1]
        if sel == "oui": return lambda x, y: x > 0 and y > 0
        return lambda x, y: x == 0 or y == 0
    if type_marche == "over_under_total":
        _, ligne, sens = cle_cote
        return (lambda x, y: (x + y) > ligne) if sens == "over" else (lambda x, y: (x + y) < ligne)
    if type_marche == "buts_equipe_domicile":
        _, ligne, sens = cle_cote
        return (lambda x, y: x > ligne) if sens == "over" else (lambda x, y: x < ligne)
    if type_marche == "buts_equipe_exterieur":
        _, ligne, sens = cle_cote
        return (lambda x, y: y > ligne) if sens == "over" else (lambda x, y: y < ligne)
    if type_marche == "parite_totale":
        sel = cle_cote[1]
        return (lambda x, y: (x + y) % 2 == 0) if sel == "pair" else (lambda x, y: (x + y) % 2 == 1)
    if type_marche == "handicap_3choix":
        _, ligne, sel = cle_cote
        if round(ligne * 4) % 2 != 0:
            return None  # ligne au quart de but -- pas une indicatrice pure, voir docstring
        h = -ligne
        if sel == "domicile": return lambda x, y: (x + h) > y
        if sel == "nul": return lambda x, y: (x + h) == y
        return lambda x, y: (x + h) < y
    if type_marche == "combo_dc_total":
        _, dc, sens, ligne = cle_cote
        cond_dc = {"1X": lambda x, y: x >= y, "X2": lambda x, y: x <= y, "12": lambda x, y: x != y}[dc]
        cond_total = (lambda x, y: (x + y) > ligne) if sens == "over" else (lambda x, y: (x + y) < ligne)
        return lambda x, y: cond_dc(x, y) and cond_total(x, y)
    return None


def _valeurs_4_scenarios(resultats_par_scenario, extracteur):
    return [extracteur(resultats_par_scenario[scenario]) for scenario in SCENARIOS]


def _stats_globales(historique_complet_equipe):
    fenetre_globale = validation.classifie_fenetre(historique_complet_equipe)
    if fenetre_globale["statut"] != validation.STATUT_UTILISABLE:
        return None, None
    stats_off = team_stats.stats_offensives(fenetre_globale["matchs_retenus"])
    stats_def = team_stats.stats_defensives(fenetre_globale["matchs_retenus"])
    return stats_off["moyenne"], stats_def["moyenne"]


def analyse_match(url_domicile, nom_domicile, url_exterieur, nom_exterieur, nom_competition):
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
    marches_par_scenario = {s: markets.calcule_tous_les_marches(lambdas["A"][s], lambdas["B"][s]) for s in SCENARIOS}

    def _extrait_1x2(issue):
        return lambda m: m["1x2"][issue] if m["1x2"] else None
    robustesse_par_marche = {
        "1x2_domicile": robustness.evalue_robustesse(_valeurs_4_scenarios(marches_par_scenario, _extrait_1x2("domicile"))),
        "1x2_nul": robustness.evalue_robustesse(_valeurs_4_scenarios(marches_par_scenario, _extrait_1x2("nul"))),
        "1x2_exterieur": robustness.evalue_robustesse(_valeurs_4_scenarios(marches_par_scenario, _extrait_1x2("exterieur"))),
        "btts": robustness.evalue_robustesse(_valeurs_4_scenarios(marches_par_scenario, lambda m: m["btts"])),
        "over_2_5": robustness.evalue_robustesse(_valeurs_4_scenarios(marches_par_scenario, lambda m: m["over_under_total"][2.5]["over"] if m["over_under_total"][2.5] else None)),
        "cage_inviolee_domicile": robustness.evalue_robustesse(_valeurs_4_scenarios(marches_par_scenario, lambda m: m["buts_equipe_exterieur"][0.5]["under"] if m["buts_equipe_exterieur"][0.5] else None)),
        "cage_inviolee_exterieur": robustness.evalue_robustesse(_valeurs_4_scenarios(marches_par_scenario, lambda m: m["buts_equipe_domicile"][0.5]["under"] if m["buts_equipe_domicile"][0.5] else None)),
        "parite_pair": robustness.evalue_robustesse(_valeurs_4_scenarios(marches_par_scenario, lambda m: m["parite_totale"]["pair"] if m["parite_totale"] else None)),
    }
    return {"statut": "OK", "fenetres": {"A": fenetre_a, "B": fenetre_b}, "lambdas": lambdas, "marches_par_scenario": marches_par_scenario, "robustesse_par_marche": robustesse_par_marche, "_historique_justification": {"A": historique_domicile, "B": historique_exterieur}}


def _par_scenario(marches_par_scenario, extracteur):
    return {s: extracteur(marches_par_scenario[s]) for s in SCENARIOS}


def _construit_candidat(*, marche, market_family, exposure_group, marches_par_scenario, extracteur, cote, robustesse_statut, n_par_scenario, h2h_palier, h2h_statut, signal, matchs_a_domicile=None, matchs_b_exterieur=None, historique_a=None, historique_b=None, confrontations_h2h=None, nom_domicile="", nom_exterieur="", cle_cote=None):
    probabilites = _par_scenario(marches_par_scenario, extracteur)
    resultat = convergence.filtre_marche_convergent(nombre_matchs_par_scenario=n_par_scenario, probabilites_par_scenario=probabilites, cote=cote, robustesse=robustesse_statut, marche=marche, market_family=market_family, exposure_group=exposure_group)
    diagnostic = {"marche": marche, "filtre": resultat.as_dict(), "h2h_statut": h2h_statut}
    if not resultat.eligible:
        return None, diagnostic
    p_repr = probabilites[SCENARIO_REPRESENTATIF]
    valeur = edv_calculator.evalue_valeur(p_repr, cote)
    return {
        "marche": marche, "market_family": market_family, "exposure_group": exposure_group,
        "niveau": resultat.resultats_par_scenario[SCENARIO_REPRESENTATIF].niveau,
        "robustesse": robustesse_statut, "probabilite": p_repr, "cote": cote,
        "edge": valeur["edge"], "edv": valeur["edv"], "h2h_palier": h2h_palier,
        "condition": _condition_pour_cle(cle_cote) if cle_cote is not None else None,
        "signal_direction": signal["direction"] if signal else None, "signal_frequence": signal["frequence"] if signal else None,
        "confirmation_historique": justification.confirmation_historique(marche, matchs_a_domicile, matchs_b_exterieur) if matchs_a_domicile is not None or matchs_b_exterieur is not None else None,
        "justification": justification.construit_justification(marche, historique_a or [], historique_b or [], h2h=confrontations_h2h or [], nom_domicile=nom_domicile, nom_exterieur=nom_exterieur),
    }, diagnostic


def _extracteur_dynamique(cle, matrices_par_scenario, dist_a_par_scenario, dist_b_par_scenario):
    if cle[0] == "1x2":
        _, sel = cle; return lambda s: markets.probabilites_1x2(matrices_par_scenario[s])[sel] if matrices_par_scenario[s] else None
    if cle[0] == "double_chance":
        _, sel = cle; return lambda s: markets.probabilites_double_chance(matrices_par_scenario[s])[sel] if matrices_par_scenario[s] else None
    if cle[0] == "btts":
        _, sel = cle
        def f(s):
            p = markets.probabilite_btts(matrices_par_scenario[s]) if matrices_par_scenario[s] else None
            return p if sel == "oui" else (1.0 - p if p is not None else None)
        return f
    if cle[0] == "parite_totale":
        _, sel = cle; return lambda s: markets.probabilite_parite_totale(matrices_par_scenario[s])[sel] if matrices_par_scenario[s] else None
    if cle[0] == "over_under_total":
        _, ligne, sens = cle
        return lambda s: (markets.probabilites_over_under_total(matrices_par_scenario[s], ligne) or {}).get(sens) if matrices_par_scenario[s] else None
    if cle[0] == "buts_equipe_domicile":
        _, ligne, sens = cle
        return lambda s: (markets.probabilites_buts_equipe(dist_a_par_scenario[s], ligne) or {}).get(sens) if dist_a_par_scenario[s] else None
    if cle[0] == "buts_equipe_exterieur":
        _, ligne, sens = cle
        return lambda s: (markets.probabilites_buts_equipe(dist_b_par_scenario[s], ligne) or {}).get(sens) if dist_b_par_scenario[s] else None
    if cle[0] == "handicap_3choix":
        _, ligne, sel = cle
        def f(s):
            if not matrices_par_scenario[s]: return None
            r = markets.resultat_handicap(matrices_par_scenario[s], -ligne)
            if not r: return None
            if sel == "domicile": return r["gain"]
            if sel == "nul": return r["push"]
            return r["perte"]
        return f
    if cle[0] == "combo_dc_total":
        _, dc, sens, ligne = cle
        return lambda s: markets.probabilite_combo_dc_total(matrices_par_scenario[s], dc, ligne, sens) if matrices_par_scenario[s] else None
    return None


def analyse_match_complet(url_domicile, nom_domicile, url_exterieur, nom_exterieur, nom_competition, match_id, url_h2h=None, chemin_precalcul="precalcul.json", cotes_info=None):
    base = analyse_match(url_domicile, nom_domicile, url_exterieur, nom_exterieur, nom_competition)
    if base["statut"] != "OK": return {"statut": base["statut"], "fenetres": base.get("fenetres")}
    confrontations = h2h_stats.recupere_confrontations(url_h2h, nom_domicile) if url_h2h else []
    fenetre_h2h = h2h_stats.classifie_h2h(confrontations)
    if cotes_info is None: cotes_info = odds_provider.recupere_cotes_pour_match(match_id, chemin_precalcul)
    if cotes_info["statut"] != "OK": return {"statut": "COTES_INDISPONIBLES", "fenetres": base["fenetres"], "match_id": match_id}
    cotes = cotes_info["cotes"]
    marches_par_scenario = base["marches_par_scenario"]
    robustesse_par_marche = base["robustesse_par_marche"]
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
    signal_buts_b_05 = statistiques_signal.signal_buts_equipe(base["fenetres"]["B"], 0.5)
    signal_buts_a_05 = statistiques_signal.signal_buts_equipe(base["fenetres"]["A"], 0.5)
    candidats, diagnostics = [], []
    _matchs_a_domicile = [m for m in base["fenetres"]["A"]["matchs_retenus"] if m.get("domicile") is True]
    _matchs_b_exterieur = [m for m in base["fenetres"]["B"]["matchs_retenus"] if m.get("domicile") is False]
    _historique_a_justif = base.get("_historique_justification", {}).get("A", [])
    _historique_b_justif = base.get("_historique_justification", {}).get("B", [])
    _h2h_justif = fenetre_h2h.get("confrontations_retenues", [])

    def ajoute(marche, family, group, extracteur, cle_cote, robustesse_key, signal, h2h_statut):
        candidat, diag = _construit_candidat(marche=marche, market_family=family, exposure_group=group, marches_par_scenario=marches_par_scenario, extracteur=extracteur, cote=cotes.get(cle_cote), robustesse_statut=robustesse_par_marche[robustesse_key]["statut"], n_par_scenario=n_par_scenario, h2h_palier=fenetre_h2h["palier"], h2h_statut=h2h_statut, signal=signal, matchs_a_domicile=_matchs_a_domicile, matchs_b_exterieur=_matchs_b_exterieur, historique_a=_historique_a_justif, historique_b=_historique_b_justif, confrontations_h2h=_h2h_justif, nom_domicile=nom_domicile, nom_exterieur=nom_exterieur, cle_cote=cle_cote)
        diagnostics.append(diag)
        if candidat is not None: candidats.append(candidat)

    ajoute("1x2_domicile", "RESULT", "GROUPE_RESULTAT", lambda m: m["1x2"]["domicile"] if m["1x2"] else None, ("1x2", "domicile"), "1x2_domicile", signal_victoire_a, statut_h2h_1x2)
    ajoute("1x2_nul", "RESULT", "GROUPE_RESULTAT", lambda m: m["1x2"]["nul"] if m["1x2"] else None, ("1x2", "nul"), "1x2_nul", None, statut_h2h_1x2)
    ajoute("1x2_exterieur", "RESULT", "GROUPE_RESULTAT", lambda m: m["1x2"]["exterieur"] if m["1x2"] else None, ("1x2", "exterieur"), "1x2_exterieur", signal_victoire_b, statut_h2h_1x2)
    ajoute("btts_oui", "BTTS", "GROUPE_BUTS", lambda m: m["btts"], ("btts", "oui"), "btts", signal_btts_a, statut_h2h_btts)
    ajoute("btts_non", "BTTS", "GROUPE_BUTS", lambda m: (1.0 - m["btts"]) if m["btts"] is not None else None, ("btts", "non"), "btts", signal_btts_a, statut_h2h_btts)
    ajoute("over_2.5", "GOALS_TOTAL", "GROUPE_BUTS", lambda m: m["over_under_total"][2.5]["over"] if m["over_under_total"][2.5] else None, ("over_under_total", 2.5, "over"), "over_2_5", signal_over25_a, statut_h2h_over25)
    ajoute("cage_inviolee_domicile", "CLEAN_SHEET_DOMICILE", "GROUPE_BUTS", lambda m: m["buts_equipe_exterieur"][0.5]["under"] if m["buts_equipe_exterieur"][0.5] else None, ("buts_equipe_exterieur", 0.5, "under"), "cage_inviolee_domicile", signal_buts_b_05, None)
    ajoute("encaisse_domicile", "CLEAN_SHEET_DOMICILE", "GROUPE_BUTS", lambda m: m["buts_equipe_exterieur"][0.5]["over"] if m["buts_equipe_exterieur"][0.5] else None, ("buts_equipe_exterieur", 0.5, "over"), "cage_inviolee_domicile", signal_buts_b_05, None)
    ajoute("cage_inviolee_exterieur", "CLEAN_SHEET_EXTERIEUR", "GROUPE_BUTS", lambda m: m["buts_equipe_domicile"][0.5]["under"] if m["buts_equipe_domicile"][0.5] else None, ("buts_equipe_domicile", 0.5, "under"), "cage_inviolee_exterieur", signal_buts_a_05, None)
    ajoute("encaisse_exterieur", "CLEAN_SHEET_EXTERIEUR", "GROUPE_BUTS", lambda m: m["buts_equipe_domicile"][0.5]["over"] if m["buts_equipe_domicile"][0.5] else None, ("buts_equipe_domicile", 0.5, "over"), "cage_inviolee_exterieur", signal_buts_a_05, None)
    ajoute("parite_pair", "PARITE", "GROUPE_BUTS", lambda m: m["parite_totale"]["pair"] if m["parite_totale"] else None, ("parite_totale", "pair"), "parite_pair", None, None)
    ajoute("parite_impair", "PARITE", "GROUPE_BUTS", lambda m: m["parite_totale"]["impair"] if m["parite_totale"] else None, ("parite_totale", "impair"), "parite_pair", None, None)

    lambdas_dyn = base["lambdas"]
    matrices_par_scenario = {s: distribution.matrice_scores(lambdas_dyn["A"][s], lambdas_dyn["B"][s]) for s in SCENARIOS}
    dist_a_par_scenario = {s: distribution.distribution_marginale(lambdas_dyn["A"][s]) for s in SCENARIOS}
    dist_b_par_scenario = {s: distribution.distribution_marginale(lambdas_dyn["B"][s]) for s in SCENARIOS}
    familles = {"1x2": ("RESULT", "GROUPE_RESULTAT"), "double_chance": ("DOUBLE_CHANCE", "GROUPE_RESULTAT"), "over_under_total": ("GOALS_TOTAL", "GROUPE_BUTS"), "buts_equipe_domicile": ("GOALS_EQUIPE_DOMICILE", "GROUPE_BUTS"), "buts_equipe_exterieur": ("GOALS_EQUIPE_EXTERIEUR", "GROUPE_BUTS"), "handicap_3choix": ("HANDICAP", "GROUPE_HANDICAP"), "combo_dc_total": ("COMBO_DC_TOTAL", "GROUPE_COMBO_DC_TOTAL"), "btts": ("BTTS", "GROUPE_BUTS"), "parite_totale": ("PARITE", "GROUPE_BUTS")}
    cles_deja = {( "1x2", "domicile"),("1x2", "nul"),("1x2", "exterieur"),("btts", "oui"),("btts", "non"),("over_under_total",2.5,"over"),("buts_equipe_exterieur",0.5,"under"),("buts_equipe_exterieur",0.5,"over"),("buts_equipe_domicile",0.5,"under"),("buts_equipe_domicile",0.5,"over"),("parite_totale","pair"),("parite_totale","impair")}
    for cle_cote, cote_reelle in cotes.items():
        if cle_cote in cles_deja or cle_cote[0] not in familles: continue
        extracteur = _extracteur_dynamique(cle_cote, matrices_par_scenario, dist_a_par_scenario, dist_b_par_scenario)
        if extracteur is None: continue
        probabilites_dyn = {s: extracteur(s) for s in SCENARIOS}
        robuste = robustness.evalue_robustesse([probabilites_dyn[s] for s in SCENARIOS])
        if not robuste: continue
        statut = robuste["statut"]
        if cle_cote[0] in ("1x2", "double_chance"):
            marche_nom = f"{cle_cote[0]}_{cle_cote[1]}"
        elif cle_cote[0] == "handicap_3choix":
            marche_nom = f"handicap_{cle_cote[2]}_{cle_cote[1]}"
        elif cle_cote[0] == "combo_dc_total":
            marche_nom = f"combo_{cle_cote[1]}_{cle_cote[2]}_{cle_cote[3]}"
        else:
            marche_nom = f"{cle_cote[0]}_{cle_cote[1]}_{cle_cote[2]}"
        family, group = familles[cle_cote[0]]
        resultat = convergence.filtre_marche_convergent(nombre_matchs_par_scenario=n_par_scenario, probabilites_par_scenario=probabilites_dyn, cote=cote_reelle, robustesse=statut, marche=marche_nom, market_family=family, exposure_group=group)
        diagnostics.append({"marche": marche_nom, "filtre": resultat.as_dict(), "h2h_statut": None})
        if resultat.eligible:
            p = probabilites_dyn[SCENARIO_REPRESENTATIF]
            valeur = edv_calculator.evalue_valeur(p, cote_reelle)
            candidats.append({"marche": marche_nom, "market_family": family, "exposure_group": group, "niveau": resultat.resultats_par_scenario[SCENARIO_REPRESENTATIF].niveau, "robustesse": statut, "probabilite": p, "cote": cote_reelle, "edge": valeur["edge"], "edv": valeur["edv"], "h2h_palier": fenetre_h2h["palier"], "condition": _condition_pour_cle(cle_cote), "signal_direction": None, "signal_frequence": None, "confirmation_historique": justification.confirmation_historique(marche_nom, _matchs_a_domicile, _matchs_b_exterieur), "justification": justification.construit_justification(marche_nom, _historique_a_justif, _historique_b_justif, h2h=_h2h_justif, nom_domicile=nom_domicile, nom_exterieur=nom_exterieur), "_cle_cote": cle_cote})

    # RÉSIDU RETIRÉ 16/09/2026 (demande explicite de Patrick, "pas de
    # résidus qui traînent") : ce bloc excluait tout candidat Combo dès
    # que sa composante Double Chance OU sa composante Total était
    # elle-même éligible séparément -- une règle BINAIRE, pas basée sur
    # la vraie corrélation, et appliquée AVANT même la déduplication,
    # donc invisible pour signals.selection_edv_directe. Elle pouvait
    # écarter à tort un Combo dont la vraie corrélation avec son
    # composant DC/Total est en réalité SOUS le seuil pour ce match
    # précis (vérifié : Double Chance 1X et Handicap domicile +1
    # peuvent être corrélés à seulement 0.56 selon les λ du match,
    # sous le seuil 0.70 -- le même principe s'applique ici). Le
    # correctif : laisser TOUS les candidats Combo atteindre
    # deduplication puis selection_edv_directe.elimine_marches_correles,
    # qui calcule la vraie corrélation match par match au lieu d'une
    # règle générique décidée à l'avance.
    for c in candidats: c.pop("_cle_cote", None)
    candidats_dedupliques = deduplication.deduplique(candidats, critere="edge") if candidats else []

    # DÉBRANCHEMENT 16/09/2026 (décision explicite de Patrick) : l'ancienne
    # cascade (signals.selector, décision du 09/09/2026) n'est plus
    # utilisée pour la sélection de production -- remplacée par
    # signals.selection_edv_directe (EDV -> probabilité -> cote,
    # corrélation de Pearson au lieu d'exposure_group pour éliminer les
    # marchés redondants). selector.py n'est PAS supprimé (gardé de
    # côté au cas où, sur demande explicite de Patrick), simplement
    # plus appelé ici.
    matrice_repr = matrices_par_scenario.get(SCENARIO_REPRESENTATIF)
    if matrice_repr is not None:
        selection = selection_edv_directe.selectionner(candidats_dedupliques, matrice_repr)
        diagnostic_selection = selection_edv_directe.diagnostique_selection(candidats_dedupliques, selection)
    else:
        # Lambda manquant en amont -- aucune matrice, donc aucune
        # sélection possible (jamais une sélection partielle ou
        # devinée). Cohérent avec le comportement déjà établi ailleurs
        # dans ce module face à une donnée manquante.
        selection = {"P1": None, "P2": None, "P3": None}
        diagnostic_selection = {"P1": {"critere": "aucune_selection"}, "P2": {"critere": "aucune_selection"}, "P3": {"critere": "aucune_selection"}}
    for rang in ("P1", "P2", "P3"): justification.enrichit_justification_selection(selection.get(rang), diagnostic_selection.get(rang))

    return {"statut":"OK", "fenetres":base["fenetres"], "lambdas":base["lambdas"], "candidats":candidats, "candidats_dedupliques":candidats_dedupliques, "selection":selection, "diagnostics":diagnostics, "h2h":{"palier":fenetre_h2h["palier"],"1x2":statut_h2h_1x2,"btts":statut_h2h_btts,"over_2.5":statut_h2h_over25}, "cotes_info":{k:v for k,v in cotes_info.items() if k != "cotes"}}
