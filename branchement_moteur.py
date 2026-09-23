#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
branchement_moteur.py -- branche moteur_v2_6_9.py sur le pipeline nocturne.

Il REMPLACE l'ancien modèle (`archetype_model.main.analyse_match_complet`), qui n'est plus appelé nulle part
dans le pipeline. Ce module ne calcule aucune probabilité : il fait le lien entre quatre contrats.

    signal du pipeline ──pont_moteur──▶ match du moteur ──moteur_v2_6_9──▶ inventaire de marchés
                                                                                   │
                       ┌───────────────────────────────────────────────────────────┘
                       ▼
    1. nom canonique du marché (celui que comprennent le règlement, la bibliothèque et le site)
    2. justification spécifique au marché (bibliotheque_justification.py) -- règle NO DATA -> NO GO
    3. sélection P1 / P2 / P3 (les trois onglets du site)
    4. bloc `moteur_v2_6_9` du signal (lu par le site) + enregistrements d'archive (SELECTED / COUNTERFACTUAL)

DÉCISIONS (à contester si elles ne conviennent pas)
    D1. Candidat = value bet du moteur (`is_value`) hors catégorie D. La catégorie D (EV > 30 % ou deux
        artefacts) est écartée PAR LE MOTEUR ; on ne la remet pas en jeu. Elle est archivée en contrefactuel.
    D2. NO DATA -> NO GO (règle maîtresse du propriétaire, 19/09/2026) : un candidat sans preuve SPÉCIFIQUE à
        son marché n'est pas retenu (motif JUSTIFICATION_INSUFFISANTE). La preuve EV, valable pour tous les
        marchés, ne suffit jamais.
    D3. Sélection : au plus trois choix, un par rôle, dans cet ordre --
          P1 favori  = probabilité modèle la plus haute            (même règle que le site : Favori du Modèle)
          P2 value   = meilleur EV parmi les restants              (Value Bet)
          P3 poker   = meilleur EV parmi les restants dont cote >= 2,91 et probabilité >= 20 %  (Coup de Poker)
        Ces règles sont celles de `remappeEnOngletsApp()` (archetype.js) : un test de contrat vérifie que le site
        retrouve exactement les mêmes rôles. Si l'une change, l'autre doit changer.
    D4. Pas de repli sur l'ancien moteur : une exception sur un match donne le statut ERREUR_TECHNIQUE pour ce
        match (visible dans le log et dans precalcul.json), jamais une décision inventée.
    D6. Échantillon minimal (règle du propriétaire, 21/09/2026) : un match n'est analysé automatiquement que si l'équipe
        qui reçoit a au moins 2 matchs À DOMICILE et la visiteuse au moins 2 matchs À L'EXTÉRIEUR cette saison (les deux
        chiffres que le moteur utilise : `matchs_joues` de chaque équipe). En dessous : refus explicite
        `echantillon_insuffisant`, avec les deux effectifs. Sinon le match est analysé, et seules les conditions
        irréfutables le refusent (pas de cotes, match commencé/reporté, cotes inexploitables, validations V1-V12 du moteur).
    D5. Niveau de solidité affiché = catégorie du moteur (A, B, C) ; il n'y a pas d'analyse de robustesse par
        scénarios avec ce moteur : `robustesse` reste None et le site n'affiche pas de « stabilité du calcul ».

Nomenclature canonique (moteur -> pipeline) : victoire/nul/defaite -> 1x2_domicile/1x2_nul/1x2_exterieur ;
dc_1X/dc_X2/dc_12 -> double_chance_* ; over_X_5 -> over_under_total_X.5_over ; buts_dom_over_X_5 ->
buts_equipe_domicile_X.5_over ; clean_sheet_dom -> cage_inviolee_domicile ;
handicap_dom_-1_5 -> handicap_domicile_-1.5 ; handicap_ext_+1_5 -> handicap_exterieur_1.5
(la ligne est celle de l'équipe NOMMÉE, sans signe « + » : c'est ce que lit le règlement).
"""
from __future__ import annotations

import datetime
import re
import sys
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import justification
import moteur_v2_6_9 as moteur
import pont_moteur

NOM_MOTEUR = "moteur_v2_6_9"
VERSION_MOTEUR = "2.6.9"
CONFIG_VERSION = "constantes_v2_6_9"
CLE_BLOC = NOM_MOTEUR            # clé du signal lue par le site (archetype.js : CLE_MOTEUR)

# D3 -- mêmes seuils que archetype.js (SEUIL_COUP_DE_POKER_COTE / SEUIL_COUP_DE_POKER_PROBA).
SEUIL_COUP_DE_POKER_COTE = 2.91
SEUIL_COUP_DE_POKER_PROBA = 0.20
RANGS = ("P1", "P2", "P3")

MIN_MATCHS_PAR_LIEU = 2                          # D6 : minimum de matchs à domicile (équipe qui reçoit) ET à l'extérieur (visiteuse)
MOTIF_ECHANTILLON = "echantillon_insuffisant"
MOTIF_JUSTIFICATION = "JUSTIFICATION_INSUFFISANTE"
MOTIF_NON_MAPPE = "MARCHE_SANS_NOM_CANONIQUE"

# ══════════════════════════════════════════════════════════════════════════
# 1. NOMENCLATURE
# ══════════════════════════════════════════════════════════════════════════
_STATIQUE: Dict[str, str] = {
    "victoire": "1x2_domicile", "nul": "1x2_nul", "defaite": "1x2_exterieur",
    "btts_oui": "btts_oui", "btts_non": "btts_non",
    "dc_1X": "double_chance_1X", "dc_X2": "double_chance_X2", "dc_12": "double_chance_12",
    "clean_sheet_dom": "cage_inviolee_domicile", "clean_sheet_ext": "cage_inviolee_exterieur",
}
_RE_OU = re.compile(r"^(over|under)_(\d)_5$")
_RE_BUTS = re.compile(r"^buts_(dom|ext)_(over|under)_(\d)_5$")
_RE_HANDICAP = re.compile(r"^handicap_(dom|ext)_([+-]?)(\d+)_(\d)$")
_COTE = {"dom": "domicile", "ext": "exterieur"}


def nom_canonique(cle_moteur: str) -> Optional[str]:
    """Clé du moteur -> nom canonique du pipeline, ou None si aucune correspondance (jamais deviné)."""
    if not isinstance(cle_moteur, str):
        return None
    if cle_moteur in _STATIQUE:
        return _STATIQUE[cle_moteur]
    m = _RE_OU.match(cle_moteur)
    if m:
        return f"over_under_total_{m.group(2)}.5_{m.group(1)}"
    m = _RE_BUTS.match(cle_moteur)
    if m:
        return f"buts_equipe_{_COTE[m.group(1)]}_{m.group(3)}.5_{m.group(2)}"
    m = _RE_HANDICAP.match(cle_moteur)
    if m:
        valeur = int(m.group(3)) + int(m.group(4)) / 10.0
        if m.group(2) == "-":
            valeur = -valeur
        if valeur == 0:
            valeur = 0.0
        return f"handicap_{_COTE[m.group(1)]}_{valeur:.1f}"
    return None


def famille_et_groupe(canon: str) -> Tuple[str, str]:
    """(market_family, exposure_group) -- taxonomie lue par l'archive et par les tickets."""
    if canon.startswith("1x2_"):
        return "RESULT", "GROUPE_RESULTAT"
    if canon.startswith("double_chance_"):
        return "DOUBLE_CHANCE", "GROUPE_RESULTAT"
    if canon.startswith("btts_"):
        return "BTTS", "GROUPE_BUTS"
    if canon.startswith("over_under_total_"):
        return "GOALS_TOTAL", "GROUPE_BUTS"
    if canon.startswith("buts_equipe_domicile_"):
        return "GOALS_EQUIPE_DOMICILE", "GROUPE_BUTS"
    if canon.startswith("buts_equipe_exterieur_"):
        return "GOALS_EQUIPE_EXTERIEUR", "GROUPE_BUTS"
    if canon.startswith("handicap_"):
        return "HANDICAP", "GROUPE_HANDICAP"
    if canon == "cage_inviolee_domicile":
        return "CLEAN_SHEET_DOMICILE", "GROUPE_BUTS"
    if canon == "cage_inviolee_exterieur":
        return "CLEAN_SHEET_EXTERIEUR", "GROUPE_BUTS"
    return "AUTRE", "GROUPE_AUTRE"


# ══════════════════════════════════════════════════════════════════════════
# 2. CANDIDATS
# ══════════════════════════════════════════════════════════════════════════
def _vigilance(artefacts: Iterable[str], avertissements_match: Iterable[str]) -> Tuple[List[str], List[str]]:
    """(points de vigilance lisibles, avertissements techniques V1-V12). Les seconds restent dans la donnée."""
    lisibles: List[str] = []
    techniques: List[str] = []
    for a in list(artefacts) + list(avertissements_match):
        if re.match(r"^V\d+\b", a):
            techniques.append(a)
        elif a not in lisibles:
            lisibles.append(a)
    return lisibles, techniques


def candidat_depuis_ligne(ligne: Dict[str, Any], canon: str, avertissements_match: Iterable[str]) -> Dict[str, Any]:
    famille, groupe = famille_et_groupe(canon)
    vigilance, techniques = _vigilance(ligne.get("artefacts") or [], avertissements_match)
    categorie = ligne.get("categorie")
    return {
        "marche": canon, "marche_moteur": ligne["marche"],
        "market_family": famille, "exposure_group": groupe,
        "probabilite": ligne["proba_modele"], "cote": ligne["cote"], "p_juste": ligne["p_juste"],
        "edge": ligne["edge"], "edv": ligne["ev"], "push": ligne.get("push", 0.0),
        "categorie": categorie, "niveau": f"CAT_{categorie}" if categorie else None, "robustesse": None,
        "statut_moteur": ligne.get("statut"), "designation": ligne.get("designation") or None,
        "points_de_vigilance": vigilance, "avertissements_techniques": techniques,
    }


def justifie(candidat: Dict[str, Any], stats_dom: Dict[str, Any], stats_ext: Dict[str, Any],
             h2h: List[Dict[str, Any]], nom_dom: str, nom_ext: str) -> Dict[str, Any]:
    """Justification de la bibliothèque, calculée sur les MÊMES matchs que ceux dont le moteur a tiré ses moyennes.
    Domicile : matchs à domicile de l'équipe qui reçoit ; extérieur : matchs à l'extérieur de la visiteuse."""
    return justification.construit_justification(
        candidat["marche"],
        (stats_dom or {}).get("matchs_domicile_bruts") or [],
        (stats_ext or {}).get("matchs_exterieur_bruts") or [],
        h2h=h2h or [],
        nom_domicile=nom_dom, nom_exterieur=nom_ext,
        odds_scraped=candidat["cote"], market_prob_pct=candidat["probabilite"] * 100.0,
    )


# ══════════════════════════════════════════════════════════════════════════
# 3. SÉLECTION (D3)
# ══════════════════════════════════════════════════════════════════════════
def _cle_favori(c: Dict[str, Any]) -> Tuple[float, float, str]:
    return (-c["probabilite"], -c["cote"], c["marche"])


def _cle_valeur(c: Dict[str, Any]) -> Tuple[float, float, str]:
    return (-c["edv"], -c["cote"], c["marche"])


def est_coup_de_poker(c: Dict[str, Any]) -> bool:
    return c["cote"] >= SEUIL_COUP_DE_POKER_COTE and c["probabilite"] >= SEUIL_COUP_DE_POKER_PROBA


def selectionne(candidats: List[Dict[str, Any]]) -> Dict[str, Optional[Dict[str, Any]]]:
    """P1 favori, P2 value, P3 coup de poker (chaque candidat n'apparaît qu'une fois). Voir D3."""
    sel: Dict[str, Optional[Dict[str, Any]]] = {r: None for r in RANGS}
    restants = list(candidats)
    if not restants:
        return sel
    favori = min(restants, key=_cle_favori)
    restants.remove(favori)
    sel["P1"] = dict(
        favori,
        rang="P1",
        selection_criterion="probabilite_maximale",
        raison_selection=(
            "P1 : probabilité modèle la plus élevée parmi les marchés éligibles "
            "et disposant d'une justification spécifique."
        ),
    )
    if restants:
        value = min(restants, key=_cle_valeur)
        restants.remove(value)
        sel["P2"] = dict(
            value,
            rang="P2",
            selection_criterion="edv_maximal_restant",
            raison_selection=(
                "P2 : EDV le plus élevé parmi les marchés éligibles restants "
                "et disposant d'une justification spécifique."
            ),
        )
    poker = [c for c in restants if est_coup_de_poker(c)]
    if poker:
        choix = min(poker, key=_cle_valeur)
        sel["P3"] = dict(
            choix,
            rang="P3",
            selection_criterion="edv_maximal_poker",
            raison_selection=(
                "P3 : EDV le plus élevé parmi les marchés restants satisfaisant "
                f"simultanément cote >= {SEUIL_COUP_DE_POKER_COTE:.2f} et "
                f"probabilité >= {SEUIL_COUP_DE_POKER_PROBA * 100:.0f} %, "
                "avec justification spécifique."
            ),
        )
    return sel


# ══════════════════════════════════════════════════════════════════════════
# 4. UN MATCH
# ══════════════════════════════════════════════════════════════════════════
def _inventaire_compact(lignes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for l in lignes:
        out.append({
            "marche": nom_canonique(l["marche"]) or l["marche"], "marche_moteur": l["marche"],
            "probabilite": l["proba_modele"], "cote": l["cote"], "edge": l["edge"], "ev": l["ev"],
            "statut": l["statut"], "is_value": l["is_value"], "categorie": l["categorie"],
        })
    return out


def bloc_non_analyse(statut: str, raison: str) -> Dict[str, Any]:
    return {"statut": statut, "raison": raison, "moteur": NOM_MOTEUR, "version_moteur": VERSION_MOTEUR, "selection": {}}


def analyse_signal(signal: Dict[str, Any], stats_equipes: Dict[Tuple[str, str], Any], maintenant: datetime.datetime,
                   h2h_fetcher: Optional[Callable[[Dict[str, Any]], List[Dict[str, Any]]]] = None
                   ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Retourne (bloc, non_selectionnes). `non_selectionnes` = value bets non retenus, pour l'archive contrefactuelle.
    Ne lève rien de prévisible : les refus sont des statuts (NON_EXPORTABLE, SKIP), pas des exceptions."""
    horodatage = maintenant.strftime("%Y-%m-%dT%H:%M:%SZ")
    match, raison = pont_moteur.match_vers_moteur(signal, stats_equipes, horodatage)
    if match is None:
        return bloc_non_analyse("NON_EXPORTABLE", raison or "inconnue"), []
    match.pop("_ignores", None)

    # D6 -- échantillon minimal, sur les deux effectifs réellement utilisés par le moteur (matchs_joues).
    nd = match["equipe_dom"].get("matchs_joues") or 0
    ne = match["equipe_ext"].get("matchs_joues") or 0
    if nd < MIN_MATCHS_PAR_LIEU or ne < MIN_MATCHS_PAR_LIEU:
        return bloc_non_analyse("NON_EXPORTABLE", (
            f"{MOTIF_ECHANTILLON}: {nd} match(s) à domicile pour {signal['domicile']}, {ne} match(s) à l'extérieur pour "
            f"{signal['exterieur']} (minimum {MIN_MATCHS_PAR_LIEU} et {MIN_MATCHS_PAR_LIEU})")), []

    res = moteur.analyser_match(match, date_run=match["date_match"], maintenant=maintenant)
    if res["statut_global"] == "SKIP":
        return bloc_non_analyse("SKIP", res.get("raison_skip") or "SKIP sans raison"), []

    avert_match = list(res["avertissements_match"])
    lignes = res["inventaire"]
    value_hors_d: List[Dict[str, Any]] = []
    non_selectionnes: List[Dict[str, Any]] = []
    rejets: List[Dict[str, str]] = []
    for l in lignes:
        if not l["is_value"]:
            continue
        canon = nom_canonique(l["marche"])
        if canon is None:
            rejets.append({"marche": l["marche"], "motif": MOTIF_NON_MAPPE})
            continue
        c = candidat_depuis_ligne(l, canon, avert_match)
        if l["categorie"] == "D":
            non_selectionnes.append(c)          # écarté par le moteur (D1) : archivé, jamais affiché
        else:
            value_hors_d.append(c)

    # D2 -- justification spécifique obligatoire. H2H demandé seulement s'il y a au moins un candidat.
    justifies: List[Dict[str, Any]] = []
    if value_hors_d:
        try:
            h2h = h2h_fetcher(signal) if h2h_fetcher else []
        except Exception as e:                  # un H2H indisponible n'est jamais une raison de perdre le match
            print(f"[moteur] H2H indisponible pour {signal.get('match_id')} : {e}", file=sys.stderr)
            h2h = []
        stats_dom = stats_equipes.get((signal["domicile"], signal["competition"]))
        stats_ext = stats_equipes.get((signal["exterieur"], signal["competition"]))
        for c in value_hors_d:
            j = justifie(c, stats_dom, stats_ext, h2h, signal["domicile"], signal["exterieur"])
            if j.get("preuve_specifique_disponible"):
                justifies.append(dict(c, justification=j))
            else:
                rejets.append({"marche": c["marche"], "motif": MOTIF_JUSTIFICATION})
                non_selectionnes.append(c)

    sel = selectionne(justifies)

    # La sélection est souveraine : tout marché présent dans sel a déjà
    # satisfait les exigences de sélection. L'absence éventuelle d'un champ
    # descriptif de cause ne peut donc jamais rétroactivement annuler le choix.
    # La justification explique le marché retenu ; elle n'est pas un filtre
    # supplémentaire après sélection.
    for choisi in sel.values():
        if choisi and isinstance(choisi.get("justification"), dict):
            choisi["justification"]["raison_selection"] = choisi.get("raison_selection")

    retenus = {c["marche"] for c in sel.values() if c}
    non_selectionnes.extend(c for c in justifies if c["marche"] not in retenus)

    bloc = {
        "statut": "OK", "moteur": NOM_MOTEUR, "version_moteur": VERSION_MOTEUR,
        "statut_global": res["statut_global"], "verdict": res["verdict"],
        "lambda_dom": res["lambda_dom"], "lambda_ext": res["lambda_ext"],
        "n_matchs_dom": res["n_matchs_dom"], "n_matchs_ext": res["n_matchs_ext"],
        "avertissements": avert_match, "avertissements_cotes": res["avertissements_cotes"],
        "marches_exclus": res["marches_exclus"], "non_reconnues": res["non_reconnues"],
        "nb_marches_evalues": len(lignes), "nb_value": sum(1 for l in lignes if l["is_value"]),
        "candidats": justifies, "rejets": rejets, "selection": sel,
        "inventaire": _inventaire_compact(lignes),
    }
    return bloc, non_selectionnes


# ══════════════════════════════════════════════════════════════════════════
# 5. TOUS LES SIGNAUX
# ══════════════════════════════════════════════════════════════════════════
def applique_moteur(signaux: List[Dict[str, Any]], stats_equipes: Dict[Tuple[str, str], Any], *,
                    maintenant: Optional[datetime.datetime] = None,
                    h2h_fetcher: Optional[Callable[[Dict[str, Any]], List[Dict[str, Any]]]] = None,
                    archiver: Optional[Callable[[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]], Any]] = None
                    ) -> Dict[str, Any]:
    """Pose sur chaque signal `moteur_utilise` et le bloc `moteur_v2_6_9`. Ne lève jamais : une exception sur un
    match devient ERREUR_TECHNIQUE (D4). Retourne un résumé imprimable."""
    maintenant = maintenant or datetime.datetime.now(datetime.timezone.utc)
    statuts: Dict[str, int] = {}
    raisons: Dict[str, int] = {}
    nb_selectionnes = nb_avec_choix = nb_archives = nb_erreurs_archive = 0
    for s in signaux:
        try:
            bloc, non_selectionnes = analyse_signal(s, stats_equipes, maintenant, h2h_fetcher)
        except Exception as e:                                  # D4 : pas de repli, un statut explicite
            bloc, non_selectionnes = bloc_non_analyse("ERREUR_TECHNIQUE", f"{type(e).__name__}: {e}"), []
        s["moteur_utilise"] = NOM_MOTEUR
        s[CLE_BLOC] = bloc
        statuts[bloc["statut"]] = statuts.get(bloc["statut"], 0) + 1
        if bloc["statut"] != "OK":
            cle = bloc.get("raison", "")
            cle = cle.split(":")[0][:60]
            raisons[f"{bloc['statut']} / {cle}"] = raisons.get(f"{bloc['statut']} / {cle}", 0) + 1
            continue
        n = sum(1 for r in RANGS if bloc["selection"].get(r))
        nb_selectionnes += n
        nb_avec_choix += 1 if n else 0
        if archiver is not None and (n or non_selectionnes):
            try:
                nb_archives += archiver(s, bloc, non_selectionnes) or 0
            except Exception as e:                              # jamais une raison d'interrompre le pipeline
                nb_erreurs_archive += 1
                print(f"[archivage] échec match {s.get('match_id')} : {type(e).__name__}: {e}", file=sys.stderr)
    return {"nb_signaux": len(signaux), "statuts": statuts, "raisons": dict(sorted(raisons.items(), key=lambda kv: -kv[1])[:8]),
            "nb_matchs_avec_choix": nb_avec_choix, "nb_choix_retenus": nb_selectionnes,
            "nb_archives": nb_archives, "nb_erreurs_archive": nb_erreurs_archive}


# ══════════════════════════════════════════════════════════════════════════
# 6. ARCHIVE (SELECTED / COUNTERFACTUAL)
# ══════════════════════════════════════════════════════════════════════════
def archive_bloc(signal: Dict[str, Any], bloc: Dict[str, Any], non_selectionnes: List[Dict[str, Any]], archive_module: Any) -> int:
    """Écrit les choix retenus (SELECTED) et les value bets non retenus (COUNTERFACTUAL) dans archive/AAAA-MM.json.
    `archive_module` = archetype_model.learning.archive (injecté : testable sans disque partagé)."""
    match = {
        "match_id": signal.get("match_id"), "date_match": signal.get("date"), "heure_match": signal.get("heure"),
        "equipe_dom": signal.get("domicile"), "equipe_ext": signal.get("exterieur"), "competition": signal.get("competition"),
    }
    selections = [bloc["selection"][r] for r in RANGS if bloc["selection"].get(r)]
    if not selections and not non_selectionnes:
        return 0
    return archive_module.enregistrer_selection_et_contrefactuels(
        match=match, selections=selections, contrefactuels=non_selectionnes,
        model_version=NOM_MOTEUR, config_version=CONFIG_VERSION,
        chemin=archive_module.chemin_archive_mensuelle(match["date_match"]),
    )


# ══════════════════════════════════════════════════════════════════════════
# 7. SORTIE ALLÉGÉE POUR LE SITE
# ══════════════════════════════════════════════════════════════════════════
def _justification_legere(j: Any) -> Any:
    """Même forme que l'ancien export : resume, preuves, donnees_suffisantes, bibliotheque (statistiques exactes)."""
    if not isinstance(j, dict):
        return j
    out = {
        "resume": j.get("resume"),
        "preuves": j.get("preuves") or [],
        "donnees_suffisantes": bool(j.get("donnees_suffisantes")),
        "raison_selection": j.get("raison_selection"),
    }
    if isinstance(j.get("bibliotheque"), dict):
        out["bibliotheque"] = j["bibliotheque"]
    return out


def bloc_leger(bloc: Any) -> Any:
    """Ce que le site lit (precalcul_leger.json) : statut, verdict et la sélection avec sa justification.
    Tout le reste (inventaire complet, candidats, rejets, avertissements) reste dans precalcul.json."""
    if not isinstance(bloc, dict):
        return bloc
    selection = {}
    for r, c in (bloc.get("selection") or {}).items():
        if isinstance(c, dict):
            selection[r] = dict(c, justification=_justification_legere(c.get("justification")))
    return {
        "statut": bloc.get("statut"), "moteur": bloc.get("moteur"), "version_moteur": bloc.get("version_moteur"),
        "statut_global": bloc.get("statut_global"), "raison": bloc.get("raison"), "selection": selection,
    }
