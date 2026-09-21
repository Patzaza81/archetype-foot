#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
moteur_v2_6_9.py — Moteur de value bets football.
Base : spec V2.6.2 (figée) + Phase 1 (vérificateurs V1-V12), V1 à V8, V10, V11 et V12 (opt-in) actives.
V9 = seuil de marchés valides (SEUIL_MIN_MARCHES, étape 3sexies).
Handicaps à ligne entière (H = 0, ±1, ±2) : marché à trois issues (source BetPawa « Handicap à 3 choix »).
    L'égalité sur la ligne PERD les paris dom et ext (pas de remboursement) : EV = P_win × cote − 1,
    p_juste = 1/cote, sans retrait de marge. Option B de la spec 2.6.2 (push remboursé, EV + P_push)
    disponible avec --handicap-push-rembourse, pour une source de type handicap asiatique.

Usage :
    python moteur_v2_6_9.py matchs.py                    # rapport console + rapport_<date>.json
    python moteur_v2_6_9.py matchs.py --complet          # affiche tout l'inventaire
    python moteur_v2_6_9.py matchs.py --sortie out.json --date 2026-09-20
    python moteur_v2_6_9.py --autotest                   # vérifie invariants et frontières

Entrée : un fichier JSON (liste de matchs ou {"matchs": [...]}) ou un fichier Python/texte
contenant `MATCHS = [...]` (lu sans exécution), au format de la Partie 2 de la spec.
Équipe : matchs_recents (liste de [buts_pour, buts_contre]) OU buts_marques_moy / buts_encaisses_moy,
    avec en option matchs_joues (entier >= 1 : nombre de matchs derrière les moyennes).
V5 : les moyennes de buts (par équipe) doivent être dans [0, 10], sinon SKIP du match.
Champs de match optionnels : cotes_prises_le (ISO 8601, V8), statut / date_match (V11).
Fiabilité : meta.fiabilite = "FALLBACK" (manuel) déclenche R3. Le moteur ne l'infère jamais.
Artefacts : R1, R2 (marché) et R3 (match). R4 et R5 sont des avertissements, hors catégorie D.
Clés de cotes reconnues :
    victoire, nul, defaite, btts_oui, btts_non, over_X_5 / under_X_5 (X = 0..5),
    buts_dom_over_X_5 / buts_dom_under_X_5, buts_ext_over_X_5 / buts_ext_under_X_5 (X = 0..1),
    clean_sheet_dom, clean_sheet_ext, dc_1X, dc_X2, dc_12,
    handicap_dom_-1_5, handicap_ext_+1_5, handicap_dom_0_0, ...

Ordre des opérations (figé) :
    DONNÉES → VALIDATION → VÉRIFICATEURS → CALCUL → VALUE → STATUT → ARTEFACTS
    → CATÉGORIE → DÉSIGNATION → VERDICT
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
import traceback
from datetime import date, datetime, timezone
from math import exp, factorial, fsum
from typing import Any, Dict, List, Optional, Set, Tuple

# ══════════════════════════════════════════════════════════════════════════
# PARTIE 9 — CONSTANTES
# ══════════════════════════════════════════════════════════════════════════
MAX_BUTS = 20
COTE_MIN_JOUABLE = 1.29
SEUIL_COTE_SUSPECTE = 100.0

SEUIL_VALUE_EDGE_MIN = 0.03

SEUIL_ECRASANT_PROBA = 0.65
SEUIL_PROXIMITE_ECRASANT = 0.60
SEUIL_FAVORI_FAIBLE = 0.50
SEUIL_FAVORI_BAS = 0.35
SEUIL_OUTSIDER_COTE = 4.0

SEUIL_SUSPECT_EV = 0.30
SAMPLE_SIZE_MIN = 5
BIAIS_ATTAQUE_DEFENSE_SEUIL = 0.50
SEUIL_MIN_MARCHES = 3

LAMBDA_MIN = 0.05
LAMBDA_MAX = 10.0

LIGNES_HANDICAP = (-2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0)
# Option hors spec V2.6.2 (candidate V2.6.3) : activée seulement avec --lignes-etendues.
LIGNES_HANDICAP_ETENDUES = (-3.0, -2.5) + LIGNES_HANDICAP + (2.5, 3.0)
LIGNES_ACTIVES = LIGNES_HANDICAP

# Partie 12 — bornes des catégories
CAT_EV_MAX_AB = 0.20
CAT_P_MIN_A = 0.45
CAT_P_MIN_B = 0.30

# Phase 1 — vérificateurs V1, V2 et V3
MARGE_GROUPE_MIN = 1.00
MARGE_GROUPE_MAX = 1.20

# V5 — bornes de plausibilité des moyennes de buts (par match, par équipe), inclusives.
MOYENNE_BUTS_MAX = 10.0

# V10 — la matrice de Poisson est tronquée à MAX_BUTS buts puis renormalisée. Si la masse perdue
# dépasse cette tolérance (λ très élevé), on l'avertit au lieu de corriger en silence.
# 1e-6 : au-dessus, l'effet devient mesurable ; en dessous (λ < ~6), c'est de l'arrondi.
TOLERANCE_NORMALISATION = 1e-6

# Handicaps à ligne entière : False = l'égalité sur la ligne perd (marché à 3 issues, défaut depuis 2.6.9) ;
# True = le push est remboursé (option B de la spec 2.6.2, handicap asiatique).
HANDICAP_ENTIER_REMBOURSE = False

# V7 — écart max P_modèle / P_marché sur le 1X2 au-delà duquel on avertit (mesuré : 3 matchs sur 19 à 0.15).
SEUIL_COHERENCE_1X2 = 0.15

# V8 — fraîcheur des cotes (champ optionnel cotes_prises_le ; absent = silencieux).
FRAICHEUR_MAX_HEURES = 24

# V11 — statuts de match non analysables (comparés en minuscules).
STATUTS_INACTIFS = {"reporte", "reporté", "annule", "annulé", "reported", "cancelled", "canceled", "postponed"}

# V12 — anti-doublon inter-run (opt-in via --cache).
FENETRE_DOUBLON_HEURES = 2
CACHE_DOUBLON = ".cache_moteur.json"

# V3 — Plausibilité cote par famille de marché.
# Détecte les cotes cassées (saisie, mauvais match, colonne inversée), pas
# la vraisemblance sportive. Une cote hors de sa fourchette est rejetée et
# signalée en avertissement.
FOURCHETTES_V3: Dict[str, Tuple[float, float]] = {
    "1X2":         (1.01,  30.0),
    "BTTS":        (1.05,  15.0),
    "OU":          (1.01, 100.0),
    "BUTS_EQUIPE": (1.01,  50.0),
    "CLEAN_SHEET": (1.05,  30.0),
    "DC":          (1.02,  15.0),
    "HANDICAP":    (1.01, 100.0),
}

# Partie 11 — décision : R4 (fenêtre) et R5 (profil asymétrique) sont des AVERTISSEMENTS
# affichés mais ne comptent PAS pour la catégorie D. Seuls R1, R2 et R3 sont des artefacts.

# ══════════════════════════════════════════════════════════════════════════
# PARTIE 2 — INVENTAIRE DES MARCHÉS
# ══════════════════════════════════════════════════════════════════════════
GROUPES: Dict[str, List[str]] = {
    "1X2": ["victoire", "nul", "defaite"],
    "BTTS": ["btts_oui", "btts_non"],
}
for _x in range(6):
    GROUPES[f"OU_{_x}_5"] = [f"over_{_x}_5", f"under_{_x}_5"]
for _x in (0, 1):
    GROUPES[f"BUTS_DOM_{_x}_5"] = [f"buts_dom_over_{_x}_5", f"buts_dom_under_{_x}_5"]
    GROUPES[f"BUTS_EXT_{_x}_5"] = [f"buts_ext_over_{_x}_5", f"buts_ext_under_{_x}_5"]

ISOLES = ("clean_sheet_dom", "clean_sheet_ext", "dc_1X", "dc_X2", "dc_12")
GROUPE_DE: Dict[str, str] = {m: g for g, ms in GROUPES.items() for m in ms}
MARCHES_STANDARD = set(GROUPE_DE) | set(ISOLES)

STATUTS_ECRASANT_JOUABLE = {"Écrasant + jouable", "Favori net + jouable"}
STATUTS_COMPROMIS = STATUTS_ECRASANT_JOUABLE | {"Proche écrasant + jouable"}


# ══════════════════════════════════════════════════════════════════════════
# PARTIE 3 — VALIDATION
# ══════════════════════════════════════════════════════════════════════════
def filtre_cotes_valides(cotes: Dict[str, Any], match_id: Any) -> Tuple[Dict[str, float], List[str]]:
    """3.1 — Une cote invalide rejette le marché, pas le match."""
    valides: Dict[str, float] = {}
    avertissements: List[str] = []
    for marche, cote in cotes.items():
        if isinstance(cote, bool) or not isinstance(cote, (int, float)):
            avertissements.append(f"[Match {match_id}] Cote non numérique ignorée : {marche}")
            continue
        if cote <= 1.0:
            avertissements.append(f"[Match {match_id}] Cote invalide ignorée : {marche} = {cote}")
            continue
        if cote > SEUIL_COTE_SUSPECTE:
            avertissements.append(f"[Match {match_id}] Cote suspecte : {marche} = {cote}")
        valides[marche] = float(cote)
    return valides, avertissements


def _entier_positif(v: Any) -> bool:
    return (not isinstance(v, bool)) and isinstance(v, (int, float)) and v >= 0 and int(v) == v


def _matchs_joues(eq: Dict[str, Any]) -> Tuple[Optional[int], Optional[str]]:
    """V4 — lit matchs_joues. Retourne (n, avertissement). Invalide (0, négatif, non entier,
    non numérique, booléen) → traité comme absent, avec avertissement."""
    v = eq.get("matchs_joues")
    if v is None:
        return None, None
    if _entier_positif(v) and v >= 1:
        return int(v), None
    return None, f"matchs_joues invalide pour {eq.get('nom')} : {v!r} (ignoré)"


def verifier_v5_moyennes(nom: Any, attaque: float, defense: float) -> None:
    """V5 — moyennes de buts dans [0, MOYENNE_BUTS_MAX]. Lève ValueError « V5 : ... » sinon.
    Appliquée aux deux sources (matchs_recents et moyennes fournies) : une équipe invalide
    = pas de couple λ = SKIP du match."""
    for v, champ in ((attaque, "buts_marques_moy"), (defense, "buts_encaisses_moy")):
        if v < 0:
            raise ValueError(f"V5 : {champ} = {v} < 0 pour {nom}")
        if v > MOYENNE_BUTS_MAX:
            raise ValueError(f"V5 : {champ} = {v} > {MOYENNE_BUTS_MAX} pour {nom}")


def preparer_equipe(eq: Any) -> Tuple[float, float, Optional[int], List[str]]:
    """3.2 / 2.1 — Retourne (attaque, défense, n_matchs, avertissements). Lève ValueError si invalide.

    Priorité pour n_matchs : matchs_recents (n = leur nombre, le détail prime, matchs_joues n'est
    pas examiné) > matchs_joues (entier >= 1) > None.
    Sans matchs_recents, les moyennes viennent de buts_marques_moy / buts_encaisses_moy.
    """
    if not isinstance(eq, dict) or not str(eq.get("nom", "")).strip():
        raise ValueError("nom d'équipe manquant")
    recents = eq.get("matchs_recents")
    if recents:
        gf: List[float] = []
        ga: List[float] = []
        for m in recents:
            if not (isinstance(m, (list, tuple)) and len(m) == 2
                    and _entier_positif(m[0]) and _entier_positif(m[1])):
                raise ValueError(f"matchs_recents invalide pour {eq.get('nom')} : {m!r}")
            gf.append(float(m[0]))
            ga.append(float(m[1]))
        att_r, def_r = fsum(gf) / len(gf), fsum(ga) / len(ga)
        verifier_v5_moyennes(eq.get("nom"), att_r, def_r)
        return att_r, def_r, len(recents), []
    a = eq.get("buts_marques_moy")
    d = eq.get("buts_encaisses_moy")
    for v, nom in ((a, "buts_marques_moy"), (d, "buts_encaisses_moy")):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(f"{nom} manquant ou non numérique pour {eq.get('nom')}")
    verifier_v5_moyennes(eq.get("nom"), float(a), float(d))
    n, avert = _matchs_joues(eq)
    return float(a), float(d), n, ([avert] if avert else [])


# ══════════════════════════════════════════════════════════════════════════
# PARTIE 3bis — VÉRIFICATEURS V1-V12 (Phase 1)
# ══════════════════════════════════════════════════════════════════════════
def verifier_v1_marge_groupe(reconnus: Dict[str, float], groupes_complets: Set[str],
                             mid: Any) -> Tuple[Set[str], Dict[str, str]]:
    """V1 — Somme marge ∈ [1.00, 1.20] pour chaque groupe complet.

    Retourne (groupes_valides, rejets) où rejets = {groupe: raison}.
    Un groupe rejeté doit être retiré de groupes_complets et ses marchés
    retirés de reconnus avant tout calcul de value.
    """
    groupes_valides: Set[str] = set()
    rejets: Dict[str, str] = {}
    for g in groupes_complets:
        somme = fsum(1.0 / reconnus[m] for m in GROUPES[g])
        if somme < MARGE_GROUPE_MIN:
            rejets[g] = f"[Match {mid}] V1 : somme marge {somme:.4f} < {MARGE_GROUPE_MIN:.2f}"
        elif somme > MARGE_GROUPE_MAX:
            rejets[g] = f"[Match {mid}] V1 : somme marge {somme:.4f} > {MARGE_GROUPE_MAX:.2f}"
        else:
            groupes_valides.add(g)
    return groupes_valides, rejets


def verifier_v2_coherence_handicap(
    handicaps: Dict[str, Tuple[str, float]],
    cotes: Dict[str, float],
    mid: Any,
) -> Tuple[Dict[str, Tuple[str, float]], List[Dict[str, Any]]]:
    """V2 — Cohérence dom/ext sur chaque demi-ligne de handicap.

    Pour chaque H demi-entier, si les deux côtés sont présents,
    vérifie que 1/c_dom + 1/c_ext ∈ [MARGE_GROUPE_MIN, MARGE_GROUPE_MAX].
    Les lignes entières (H = 0, ±1, ±2) sont hors périmètre car la vérification
    exigerait aussi le nul sur la ligne, que le moteur ne traite pas.
    """
    par_ligne: Dict[float, Dict[str, str]] = {}
    for cle, (side, H) in handicaps.items():
        par_ligne.setdefault(H, {})[side] = cle

    a_rejeter: Set[str] = set()
    exclusions: List[Dict[str, Any]] = []
    for H, cotes_par_side in par_ligne.items():
        if H == int(H):
            continue  # ligne entière : vérification nécessiterait le nul, non traité
        if "dom" not in cotes_par_side or "ext" not in cotes_par_side:
            continue  # paire incomplète : rien à vérifier
        cle_dom = cotes_par_side["dom"]
        cle_ext = cotes_par_side["ext"]
        c_dom = cotes[cle_dom]
        c_ext = cotes[cle_ext]
        somme = 1.0 / c_dom + 1.0 / c_ext
        if not (MARGE_GROUPE_MIN <= somme <= MARGE_GROUPE_MAX):
            raison = (
                f"[Match {mid}] V2 : ligne H={H:+.1f} incohérente — "
                f"1/c_dom ({c_dom:.2f}) + 1/c_ext ({c_ext:.2f}) = {somme:.4f} "
                f"hors [{MARGE_GROUPE_MIN:.2f}, {MARGE_GROUPE_MAX:.2f}]"
            )
            a_rejeter.update((cle_dom, cle_ext))
            exclusions.extend([
                {"marche": cle_dom, "cote": c_dom, "groupe": f"H={H:+.1f}", "raison": raison},
                {"marche": cle_ext, "cote": c_ext, "groupe": f"H={H:+.1f}", "raison": raison},
            ])
    return {cle: v for cle, v in handicaps.items() if cle not in a_rejeter}, exclusions


def _famille_marche(cle: str) -> Optional[str]:
    """Retourne la famille de marché d'une clé, ou None si non reconnue."""
    if cle in ("victoire", "nul", "defaite"):
        return "1X2"
    if cle in ("btts_oui", "btts_non"):
        return "BTTS"
    if cle.startswith("over_") or cle.startswith("under_"):
        return "OU"
    if cle.startswith("buts_dom_") or cle.startswith("buts_ext_"):
        return "BUTS_EQUIPE"
    if cle.startswith("clean_sheet_"):
        return "CLEAN_SHEET"
    if cle.startswith("dc_"):
        return "DC"
    if cle.startswith("handicap_"):
        return "HANDICAP"
    return None


def verifier_v3_plausibilite(
    cotes: Dict[str, float],
    marches_actifs: Set[str],
    mid: Any,
) -> Tuple[Set[str], List[Dict[str, Any]], List[str]]:
    """V3 — Plausibilité de chaque cote selon sa famille.

    Pour chaque marché actif (dans reconnus ou handicaps), compare la cote
    à la fourchette [min, max] de sa famille. Hors fourchette → rejet du
    marché ET émission d'un avertissement.

    Retourne (marches_a_rejeter, exclusions, avertissements).
    """
    a_rejeter: Set[str] = set()
    exclusions: List[Dict[str, Any]] = []
    avertissements: List[str] = []
    for cle in sorted(marches_actifs):
        if cle not in cotes:
            continue
        cote = cotes[cle]
        famille = _famille_marche(cle)
        if famille is None or famille not in FOURCHETTES_V3:
            continue
        cmin, cmax = FOURCHETTES_V3[famille]
        if cote < cmin or cote > cmax:
            a_rejeter.add(cle)
            exclusions.append({
                "marche": cle, "cote": cote, "groupe": famille,
                "raison": (f"[Match {mid}] V3 : {cle} (cote {cote:.2f}) hors "
                           f"[{cmin:.2f}, {cmax:.2f}] pour la famille {famille}"),
            })
            avertissements.append(
                f"[Match {mid}] V3 : {cle} = {cote:.2f} hors [{cmin:.2f}, {cmax:.2f}] ({famille})"
            )
    return a_rejeter, exclusions, avertissements


def verifier_v4_fiabilite(match: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """V4 — Fiabilité des données du match. Fonction pure, annotation (aucun rejet).

    Retourne (fiabilite, origine). Aujourd'hui, seule source : meta.fiabilite posé à la main
    (ou par le scraper) → (valeur normalisée, "meta"). Sinon (None, None).
    Le moteur n'infère JAMAIS FALLBACK depuis la forme des données : présence ou absence de
    matchs_recents ne prouve rien, et une incohérence de cache doit être marquée à la source.
    Toute valeur "FALLBACK" déclenche R3, quelle qu'en soit l'origine.
    """
    meta = match.get("meta")
    valeur = meta.get("fiabilite") if isinstance(meta, dict) else None
    if isinstance(valeur, str) and valeur.strip():
        return valeur.strip().upper(), "meta"
    return None, None


def verifier_v7_coherence_1x2(probas: Dict[str, float], reconnus: Dict[str, float],
                              groupes_complets: Set[str]) -> Tuple[Optional[float], List[str]]:
    """V7 — écart max entre P_modèle et P_marché (marge retirée) sur le 1X2. Avertissement, pas rejet."""
    if "1X2" not in groupes_complets:
        return None, []
    s = fsum(1.0 / reconnus[m] for m in GROUPES["1X2"])
    ecarts = {m: abs(probas[m] - (1.0 / reconnus[m]) / s) for m in GROUPES["1X2"]}
    ecart_max = max(ecarts.values())
    if ecart_max > SEUIL_COHERENCE_1X2:
        detail = ", ".join(f"{m}={ecarts[m]:.3f}" for m in GROUPES["1X2"])
        return ecart_max, [f"V7 : écart modèle/marché 1X2 = {ecart_max:.3f} > {SEUIL_COHERENCE_1X2:.2f} ({detail})"]
    return ecart_max, []


def verifier_v8_fraicheur(match: Dict[str, Any], maintenant: datetime, mid: Any) -> List[str]:
    """V8 — fraîcheur des cotes. Avertissement uniquement. Champ absent = silencieux (optionnel).
    Un horodatage sans fuseau est lu comme UTC."""
    brut = match.get("cotes_prises_le")
    if brut is None or (isinstance(brut, str) and not brut.strip()):
        return []
    if not isinstance(brut, str):
        return [f"[Match {mid}] V8 : cotes_prises_le illisible ({brut!r})"]
    try:
        t = datetime.fromisoformat(brut.strip())
    except ValueError:
        return [f"[Match {mid}] V8 : cotes_prises_le illisible ({brut!r})"]
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    age_h = (maintenant - t).total_seconds() / 3600.0
    if age_h > FRAICHEUR_MAX_HEURES:
        return [f"[Match {mid}] V8 : cotes vieilles de {age_h:.1f} h (> {FRAICHEUR_MAX_HEURES} h)"]
    if age_h < -1:
        return [f"[Match {mid}] V8 : horodatage des cotes dans le futur ({age_h:.1f} h)"]
    return []


def verifier_v11_statut_match(match: Dict[str, Any], date_run: str, mid: Any) -> Tuple[bool, Optional[str]]:
    """V11 — match reporté/annulé → non analysé. date_run vide = pas de contrôle de date."""
    st = match.get("statut")
    if isinstance(st, str) and st.strip().lower() in STATUTS_INACTIFS:
        return False, f"[Match {mid}] V11 : statut = {st!r}"
    dm = match.get("date_match")
    if date_run and isinstance(dm, str) and dm.strip() and dm.strip() != date_run:
        return False, f"[Match {mid}] V11 : date_match = {dm!r} ≠ date du run ({date_run})"
    return True, None


# ══════════════════════════════════════════════════════════════════════════
# PARTIES 4 & 5 — λ ET MATRICE DE POISSON
# ══════════════════════════════════════════════════════════════════════════
def calcul_lambdas_trace(att_dom: float, def_dom: float, att_ext: float, def_ext: float
                         ) -> Tuple[float, float, Dict[str, Dict[str, Any]]]:
    """V6 — λ bornés dans [LAMBDA_MIN, LAMBDA_MAX], avec trace du clamp par côté."""
    ld_brut = (att_dom + def_ext) / 2.0
    le_brut = (att_ext + def_dom) / 2.0
    ld = max(LAMBDA_MIN, min(LAMBDA_MAX, ld_brut))
    le = max(LAMBDA_MIN, min(LAMBDA_MAX, le_brut))
    clamps = {
        "dom": {"brut": ld_brut, "clampe": ld, "clamp_applique": ld != ld_brut},
        "ext": {"brut": le_brut, "clampe": le, "clamp_applique": le != le_brut},
    }
    return ld, le, clamps


def calcul_lambdas(att_dom: float, def_dom: float, att_ext: float, def_ext: float) -> Tuple[float, float]:
    ld, le, _ = calcul_lambdas_trace(att_dom, def_dom, att_ext, def_ext)
    return ld, le


def poisson(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam ** k) * exp(-lam) / factorial(k)


def masse_avant_normalisation(lam_dom: float, lam_ext: float) -> float:
    """V10 — somme de la matrice tronquée à MAX_BUTS avant renormalisation (1.0 = aucune perte)."""
    n = MAX_BUTS + 1
    return fsum(poisson(i, lam_dom) for i in range(n)) * fsum(poisson(j, lam_ext) for j in range(n))


def verifier_v10_normalisation(lam_dom: float, lam_ext: float) -> List[str]:
    """V10 — avertit si la renormalisation corrige plus que TOLERANCE_NORMALISATION."""
    masse = masse_avant_normalisation(lam_dom, lam_ext)
    ecart = abs(1.0 - masse)
    if ecart > TOLERANCE_NORMALISATION:
        return [f"V10 : masse Poisson tronquée à {MAX_BUTS} buts = {masse:.6f} (écart {ecart:.1e}), "
                f"matrice renormalisée"]
    return []


def construire_matrice(lam_dom: float, lam_ext: float) -> List[List[float]]:
    n = MAX_BUTS + 1
    pd = [poisson(i, lam_dom) for i in range(n)]
    pe = [poisson(j, lam_ext) for j in range(n)]
    mat = [[pd[i] * pe[j] for j in range(n)] for i in range(n)]
    total = fsum(c for row in mat for c in row)
    return [[c / total for c in row] for row in mat]


# ══════════════════════════════════════════════════════════════════════════
# PARTIE 6 — PROBABILITÉS PAR MARCHÉ
# ══════════════════════════════════════════════════════════════════════════
def _somme(mat: List[List[float]], cond) -> float:
    n = len(mat)
    return fsum(mat[i][j] for i in range(n) for j in range(n) if cond(i, j))


def probas_standard(mat: List[List[float]]) -> Dict[str, float]:
    p: Dict[str, float] = {}
    p["victoire"] = _somme(mat, lambda i, j: i > j)
    p["nul"] = _somme(mat, lambda i, j: i == j)
    p["defaite"] = _somme(mat, lambda i, j: i < j)
    p["dc_1X"] = p["victoire"] + p["nul"]
    p["dc_X2"] = p["nul"] + p["defaite"]
    p["dc_12"] = p["victoire"] + p["defaite"]
    for x in range(6):
        L = x + 0.5
        over = _somme(mat, lambda i, j, L=L: (i + j) > L)
        p[f"over_{x}_5"] = over
        p[f"under_{x}_5"] = 1.0 - over
    p["btts_oui"] = _somme(mat, lambda i, j: i > 0 and j > 0)
    p["btts_non"] = 1.0 - p["btts_oui"]
    p["clean_sheet_dom"] = _somme(mat, lambda i, j: j == 0)   # l'extérieur ne marque pas
    p["clean_sheet_ext"] = _somme(mat, lambda i, j: i == 0)   # le domicile ne marque pas
    for x in (0, 1):
        od = _somme(mat, lambda i, j, x=x: i > x)
        oe = _somme(mat, lambda i, j, x=x: j > x)
        p[f"buts_dom_over_{x}_5"] = od
        p[f"buts_dom_under_{x}_5"] = 1.0 - od
        p[f"buts_ext_over_{x}_5"] = oe
        p[f"buts_ext_under_{x}_5"] = 1.0 - oe
    return p


def handicap_probas(mat: List[List[float]], H: float) -> Tuple[float, float, float]:
    """6.7 — (P_win_dom, P_push, P_win_ext) pour la ligne H appliquée au domicile.

    s = (i - j) + H ; comparaisons exactes (multiples de 0.5, exactement représentables).
    """
    win_dom = _somme(mat, lambda i, j: (i - j) + H > 0)
    push = _somme(mat, lambda i, j: (i - j) + H == 0)
    win_ext = _somme(mat, lambda i, j: (i - j) + H < 0)
    return win_dom, push, win_ext


def parse_handicap_key(cle: str) -> Optional[Tuple[str, float]]:
    """'handicap_dom_-1_5' -> ('dom', -1.5). None si le format est invalide."""
    parts = cle.split("_")
    if len(parts) != 4 or parts[0] != "handicap" or parts[1] not in ("dom", "ext"):
        return None
    try:
        ligne = float(parts[2] + "." + parts[3])
    except ValueError:
        return None
    return parts[1], ligne


# ══════════════════════════════════════════════════════════════════════════
# PARTIES 8 & 9 — EDGE, EV, DÉCISION DE VALUE
# ══════════════════════════════════════════════════════════════════════════
def seuil_ev_min(cote: float) -> float:
    if cote < 2.50:
        return 0.06
    if cote < 3.50:
        return 0.07
    return 0.09


def seuil_edge_min(cote: float) -> float:
    return seuil_ev_min(cote) / cote


def evaluer_ligne(marche: str, p: float, cote: float, p_base: float, p_push: float,
                  remboursement_push: bool = True) -> Dict[str, Any]:
    """8.1-8.3. remboursement_push=False : l'égalité sur la ligne perd (marché à 3 issues) →
    p_juste = p_base, EV = p × cote − 1 ; `push` reste renseigné (probabilité modèle de l'égalité)."""
    if remboursement_push:
        p_juste = (1.0 - p_push) * p_base        # 8.1
        ev = p * cote - 1.0 + p_push             # 8.3
    else:
        p_juste = p_base
        ev = p * cote - 1.0
    edge = p - p_juste                            # 8.2
    edge_min = max(SEUIL_VALUE_EDGE_MIN, seuil_edge_min(cote))
    ev_min = seuil_ev_min(cote)
    is_value = (cote >= COTE_MIN_JOUABLE and edge >= edge_min and ev >= ev_min)
    return {
        "marche": marche, "proba_modele": p, "p_juste": p_juste, "cote": cote,
        "edge": edge, "ev": ev, "push": p_push, "statut": "", "is_value": is_value,
        "designation": "", "categorie": None, "artefacts": [],
    }


# ══════════════════════════════════════════════════════════════════════════
# PARTIE 10 — STATUTS
# ══════════════════════════════════════════════════════════════════════════
def statut_1x2(p: float, cote: float, is_value: bool) -> str:
    """Table 10.2 — victoire et defaite."""
    if cote < COTE_MIN_JOUABLE:
        return "Favori net mais injouable" if p >= SEUIL_ECRASANT_PROBA else "Injouable"
    if p >= SEUIL_ECRASANT_PROBA:
        return "Favori net + jouable" if is_value else "Favori net mais EV insuffisant"
    if p >= SEUIL_FAVORI_FAIBLE:
        return "Favori + value" if is_value else "Favori"
    if p >= SEUIL_FAVORI_BAS:
        return "Favori faible"
    if cote > SEUIL_OUTSIDER_COTE:
        return "Outsider"
    return "Favori faible"


def statut_autres(p: float, cote: float, is_value: bool) -> str:
    """Table 10.3 — tous les autres marchés (nul, DC, BTTS, O/U, buts équipe, CS, handicaps)."""
    if cote < COTE_MIN_JOUABLE:
        return "Injouable"
    if p >= SEUIL_ECRASANT_PROBA:
        return "Écrasant + jouable" if is_value else "Écrasant mais EV insuffisant"
    if p >= SEUIL_PROXIMITE_ECRASANT:
        return "Proche écrasant + jouable" if is_value else "Proche écrasant"
    return "Value crédible" if is_value else "Pas écrasant"


# ══════════════════════════════════════════════════════════════════════════
# PARTIE 11 — ARTEFACTS
# ══════════════════════════════════════════════════════════════════════════
def biais_asymetrique(equipes: List[Tuple[float, float]]) -> bool:
    """R5 — profil attaque/défense très asymétrique (jamais « biais dom/ext »)."""
    for a, d in equipes:
        m = max(a, d)
        if m > 0 and abs(a - d) / m > BIAIS_ATTAQUE_DEFENSE_SEUIL:
            return True
    return False


def artefacts_match(ctx: Dict[str, Any]) -> List[str]:
    """R3 — seul artefact de niveau match ; appliqué à tous les value bets du match."""
    arts: List[str] = []
    if ctx["fiabilite"] == "FALLBACK":
        arts.append("Données issues du classement uniquement")
    return arts


def avertissements_match(ctx: Dict[str, Any]) -> List[str]:
    """R4, R5 — avertissements de match : affichés, mais hors catégorie D."""
    avs: List[str] = []
    nd, ne = ctx["n_matchs_dom"], ctx["n_matchs_ext"]
    if nd is None or ne is None:
        avs.append("Fenêtre d'analyse inconnue")
    elif nd < SAMPLE_SIZE_MIN or ne < SAMPLE_SIZE_MIN:
        avs.append("Fenêtre d'analyse trop courte")
    if ctx["biais_attaque_defense"]:
        avs.append("Profil attaque/défense très asymétrique")
    return avs


def artefacts_marche(ligne: Dict[str, Any]) -> List[str]:
    """R1, R2 — niveau marché."""
    arts: List[str] = []
    if ligne["ev"] > SEUIL_SUSPECT_EV:
        arts.append("EV > 30 % = artefact probable")
    if (ligne["marche"] in ("victoire", "defaite")
            and ligne["proba_modele"] < SEUIL_FAVORI_BAS
            and ligne["cote"] > SEUIL_OUTSIDER_COTE):
        arts.append("Outsider rejeté par le marché")
    return arts


# ══════════════════════════════════════════════════════════════════════════
# PARTIE 12 — CATÉGORIES (ordre D → A → B → C)
# ══════════════════════════════════════════════════════════════════════════
def categorie_value(ev: float, p: float, n_arts: int) -> str:
    if ev > SEUIL_SUSPECT_EV or n_arts >= 2:
        return "D"
    if ev <= CAT_EV_MAX_AB and p >= CAT_P_MIN_A and n_arts == 0:
        return "A"
    if ev <= CAT_EV_MAX_AB and p >= CAT_P_MIN_B and n_arts <= 1:
        return "B"
    return "C"


# ══════════════════════════════════════════════════════════════════════════
# PARTIES 13 & 14 — DÉSIGNATIONS ET VERDICT
# ══════════════════════════════════════════════════════════════════════════
def _cle_tri(l: Dict[str, Any]) -> Tuple[float, float, str]:
    return (-l["proba_modele"], -l["cote"], l["marche"])


def meilleur_compromis(lignes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    comp = [l for l in lignes if l["statut"] in STATUTS_COMPROMIS and l["categorie"] != "D"]
    if not comp:
        return None
    return min(comp, key=lambda l: (-l["edge"], -l["cote"], l["marche"]))


def attribuer_designations(lignes: List[Dict[str, Any]]) -> None:
    tags: Dict[int, List[str]] = {}
    bc = meilleur_compromis(lignes)
    if bc is not None:
        tags.setdefault(id(bc), []).append("Meilleur compromis")
    values_non_d = [l for l in lignes if l["is_value"] and l["categorie"] != "D"]
    if values_non_d:
        be = min(values_non_d, key=lambda l: (-l["ev"], -l["cote"], l["marche"]))
        tags.setdefault(id(be), []).append("Meilleur EV")
    for l in lignes:
        l["designation"] = ", ".join(tags.get(id(l), []))


def _pct(x: float) -> str:
    return f"{x * 100:.1f} %"


def _spct(x: float) -> str:
    return f"{x * 100:+.1f} %"


def construire_verdict(lignes: List[Dict[str, Any]], ld: float, le: float
                       ) -> Tuple[str, str, Optional[Dict[str, Any]]]:
    """Retourne (statut_global, texte, ecrasant_principal). `lignes` doit être triée."""
    ecr = [l for l in lignes if l["statut"] in STATUTS_ECRASANT_JOUABLE and l["categorie"] != "D"]
    if ecr:
        m = ecr[0]  # premier dans l'ordre (P desc, cote desc, alpha)
        texte = (f"Le marché écrasant jouable est {m['marche']} à {_pct(m['proba_modele'])} "
                 f"(cote {m['cote']:.2f}).\n"
                 f"Modèle : λ dom {ld:.3f} / λ ext {le:.3f} ; probabilité implicite du marché "
                 f"{_pct(m['p_juste'])}, edge {_spct(m['edge'])}, EV {_spct(m['ev'])}.")
        principal = {k: m[k] for k in ("marche", "proba_modele", "cote", "edge", "ev", "push",
                                        "statut", "categorie", "designation", "artefacts")}
        principal["proba"] = principal.pop("proba_modele")
        return "ECRASANT_JOUABLE", texte, principal
    bc = meilleur_compromis(lignes)
    if bc is not None:
        texte = ("Aucun marché écrasant exploitable.\n"
                 f"Meilleur compromis : {bc['marche']} à {bc['cote']:.2f} "
                 f"(P modèle {_pct(bc['proba_modele'])}, edge {_spct(bc['edge'])}, EV {_spct(bc['ev'])}).")
        return "COMPROMIS", texte, None

    texte = "Aucun marché écrasant ni compromis (P ≥ 0.60) exploitable au sens des seuils actuels."
    values = [l for l in lignes if l["is_value"]]
    values_non_d = [l for l in values if l["categorie"] != "D"]
    if values_non_d:
        be = min(values_non_d, key=lambda l: (-l["ev"], -l["cote"], l["marche"]))
        texte += (f"\nValue bets hors compromis : {len(values_non_d)}, "
                  f"meilleur EV : {be['marche']} (EV {_spct(be['ev'])}).")
    elif values:
        texte += f"\nValue bets hors compromis : {len(values)} (tous classés D)."
    texte += "\nÉvaluation du pricing : voir cohérence marché."
    return "AUCUN", texte, None


# ══════════════════════════════════════════════════════════════════════════
# PARTIE 15 — COHÉRENCE MARCHÉ
# ══════════════════════════════════════════════════════════════════════════
def coherence_marche(lignes: List[Dict[str, Any]], groupes_complets: Set[str]) -> Dict[str, Any]:
    par_marche = {l["marche"]: l for l in lignes}
    ecart_1x2 = ecart_ou = ecart_btts = None
    if "1X2" in groupes_complets:
        ecart_1x2 = fsum(abs(par_marche[m]["proba_modele"] - par_marche[m]["p_juste"])
                         for m in ("victoire", "nul", "defaite")) / 3.0
    if "OU_2_5" in groupes_complets:
        l = par_marche["over_2_5"]
        ecart_ou = abs(l["proba_modele"] - l["p_juste"])
    if "BTTS" in groupes_complets:
        l = par_marche["btts_oui"]
        ecart_btts = abs(l["proba_modele"] - l["p_juste"])
    presents = [e for e in (ecart_1x2, ecart_ou, ecart_btts) if e is not None]
    if len(presents) < 2:
        return {"ecart_1X2": ecart_1x2, "ecart_ou_2_5": ecart_ou, "ecart_btts": ecart_btts,
                "ecart_global": None, "verdict": "Non calculable"}
    g = max(presents)
    verdict = ("correctement pricé" if g < 0.03 else "légèrement biaisé" if g < 0.08
               else "nettement biaisé")
    return {"ecart_1X2": ecart_1x2, "ecart_ou_2_5": ecart_ou, "ecart_btts": ecart_btts,
            "ecart_global": g, "verdict": verdict}


# ══════════════════════════════════════════════════════════════════════════
# PARTIE 16 — ALGORITHME PAR MATCH
# ══════════════════════════════════════════════════════════════════════════
def resultat_vide(match: Dict[str, Any]) -> Dict[str, Any]:
    """Squelette de résultat (SKIP par défaut). Source unique du schéma du rapport."""
    return {
        "id": match.get("id"), "nom_dom": match.get("nom_dom"), "nom_ext": match.get("nom_ext"),
        "lambda_dom": None, "lambda_ext": None, "clamps_lambda": None, "statut_global": "SKIP",
        "ecrasant_principal": None, "inventaire": [], "coherence_marche": None,
        "coherence_1x2_modele": None,
        "n_matchs_dom": None, "n_matchs_ext": None, "biais_attaque_defense": False,
        "fiabilite": None, "fiabilite_origine": None,
        "avertissements_cotes": [], "non_reconnues": [], "marches_exclus": [],
        "artefacts_match": [], "avertissements_match": [], "verdict": "", "raison_skip": None,
    }


def analyser_match(match: Dict[str, Any], date_run: str = "",
                   maintenant: Optional[datetime] = None) -> Dict[str, Any]:
    mid = match.get("id")
    res = resultat_vide(match)
    maintenant = maintenant or datetime.now(timezone.utc)

    # 0. V11 — match reporté/annulé : pas d'analyse
    actif, raison_v11 = verifier_v11_statut_match(match, date_run, mid)
    if not actif:
        res["raison_skip"] = raison_v11
        return res

    # 1. Filtrage des cotes (rejet marché par marché)
    cotes_valides, avert = filtre_cotes_valides(match.get("cotes") or {}, mid)
    res["avertissements_cotes"] = avert + verifier_v8_fraicheur(match, maintenant, mid)

    # 2. Validation des équipes
    try:
        att_d, def_d, n_d, av_d = preparer_equipe(match.get("equipe_dom"))
        att_e, def_e, n_e, av_e = preparer_equipe(match.get("equipe_ext"))
    except ValueError as e:
        res["raison_skip"] = f"Équipe invalide ou sans données : {e}"
        return res
    res["n_matchs_dom"], res["n_matchs_ext"] = n_d, n_e

    # 3. Classification des cotes
    reconnus: Dict[str, float] = {}
    handicaps: Dict[str, Tuple[str, float]] = {}   # clé -> (côté, H appliqué au domicile)
    non_reconnues: List[str] = []
    for cle, cote in cotes_valides.items():
        if cle in MARCHES_STANDARD:
            reconnus[cle] = cote
        elif cle.startswith("handicap_"):
            parsed = parse_handicap_key(cle)
            if parsed is None:
                non_reconnues.append(cle)
                continue
            cote_side, ligne = parsed
            H = ligne if cote_side == "dom" else -ligne
            if H not in LIGNES_ACTIVES:
                non_reconnues.append(cle)
                continue
            handicaps[cle] = (cote_side, H)
        else:
            non_reconnues.append(cle)
    res["non_reconnues"] = non_reconnues

    # 3bis. Groupes complets (nécessaire à V1 et aux avertissements « groupe incomplet »)
    groupes_complets: Set[str] = set()
    for g, membres in GROUPES.items():
        presents = [m for m in membres if m in reconnus]
        if len(presents) == len(membres):
            groupes_complets.add(g)
        elif presents:
            res["avertissements_cotes"].append(
                f"[Match {mid}] Groupe {g} incomplet : marchés traités comme isolés (p_base = 1/cote)")

    # 3ter. V1 — marge des groupes complets
    groupes_valides_v1, rejets_v1 = verifier_v1_marge_groupe(reconnus, groupes_complets, mid)
    for g, raison in rejets_v1.items():
        for m in GROUPES[g]:
            if m in reconnus:
                res["marches_exclus"].append({
                    "marche": m, "cote": reconnus[m], "groupe": g, "raison": raison,
                })
                del reconnus[m]
    groupes_complets = groupes_valides_v1

    # 3quater. V2 — cohérence dom/ext sur les demi-lignes de handicap
    handicaps, exclusions_v2 = verifier_v2_coherence_handicap(handicaps, cotes_valides, mid)
    res["marches_exclus"].extend(exclusions_v2)

    # 3quinquies. V3 — plausibilité cote par marché
    marches_actifs = set(reconnus) | set(handicaps)
    marches_v3, exclusions_v3, avertissements_v3 = verifier_v3_plausibilite(
        cotes_valides, marches_actifs, mid)
    res["marches_exclus"].extend(exclusions_v3)
    res["avertissements_cotes"].extend(avertissements_v3)
    for cle in marches_v3:
        reconnus.pop(cle, None)
        handicaps.pop(cle, None)
    # Si V3 a cassé un groupe, on revient au traitement isolé pour ce groupe
    groupes_complets = {g for g in groupes_complets
                        if all(m in reconnus for m in GROUPES[g])}

    # 3sexies. Seuil de marchés reconnus (après application de V1, V2 et V3)
    if len(reconnus) + len(handicaps) < SEUIL_MIN_MARCHES:
        n_rejets = len(rejets_v1) + len(exclusions_v2) + len(exclusions_v3)
        prefixe = "V1/V2/V3 ont laissé " if n_rejets else "Moins de "
        res["raison_skip"] = (
            f"{prefixe}{SEUIL_MIN_MARCHES} marchés valides et reconnus "
            f"({len(reconnus) + len(handicaps)})"
            + (f", {n_rejets} exclusion(s) par V1/V2/V3" if n_rejets else "")
        )
        return res

    # 4. Calcul mathématique
    ld, le, clamps = calcul_lambdas_trace(att_d, def_d, att_e, def_e)
    res["lambda_dom"], res["lambda_ext"], res["clamps_lambda"] = ld, le, clamps
    av_clamp = [f"V6 : λ {cote} clampé, brut {c['brut']:.3f} → {c['clampe']:.3f}"
                for cote, c in clamps.items() if c["clamp_applique"]]
    av_v10 = verifier_v10_normalisation(ld, le)
    mat = construire_matrice(ld, le)
    probas = probas_standard(mat)
    ecart_v7, av_v7 = verifier_v7_coherence_1x2(probas, reconnus, groupes_complets)
    res["coherence_1x2_modele"] = ecart_v7

    # 5. Value
    lignes: List[Dict[str, Any]] = []
    for marche, cote in reconnus.items():
        g = GROUPE_DE.get(marche)
        if g in groupes_complets:
            s = fsum(1.0 / reconnus[m] for m in GROUPES[g])
            p_base = (1.0 / cote) / s
        else:
            p_base = 1.0 / cote
        lignes.append(evaluer_ligne(marche, probas[marche], cote, p_base, 0.0))
    cache_h: Dict[float, Tuple[float, float, float]] = {}
    for cle, (cote_side, H) in handicaps.items():
        if H not in cache_h:
            cache_h[H] = handicap_probas(mat, H)
        wd, push, we = cache_h[H]
        p = wd if cote_side == "dom" else we
        cote = cotes_valides[cle]
        lignes.append(evaluer_ligne(cle, p, cote, 1.0 / cote, push,   # 7.4 : pas de retrait de marge
                                     remboursement_push=HANDICAP_ENTIER_REMBOURSE))

    # 6. Statut (reçoit is_value)
    for l in lignes:
        if l["marche"] in ("victoire", "defaite"):
            l["statut"] = statut_1x2(l["proba_modele"], l["cote"], l["is_value"])
        else:
            l["statut"] = statut_autres(l["proba_modele"], l["cote"], l["is_value"])

    # 7. Artefacts + 8. Catégories (value bets uniquement)
    fiabilite, fiabilite_origine = verifier_v4_fiabilite(match)
    res["fiabilite"], res["fiabilite_origine"] = fiabilite, fiabilite_origine
    ctx = {
        "fiabilite": fiabilite,
        "n_matchs_dom": n_d, "n_matchs_ext": n_e,
        "biais_attaque_defense": biais_asymetrique([(att_d, def_d), (att_e, def_e)]),
    }
    arts_m = artefacts_match(ctx)
    res["biais_attaque_defense"] = ctx["biais_attaque_defense"]
    res["artefacts_match"] = arts_m
    res["avertissements_match"] = avertissements_match(ctx) + av_d + av_e + av_clamp + av_v10 + av_v7
    for l in lignes:
        if l["is_value"]:
            l["artefacts"] = arts_m + artefacts_marche(l)
            l["categorie"] = categorie_value(l["ev"], l["proba_modele"], len(l["artefacts"]))

    # 9. Tri, 10. Désignations, 11. Verdict
    lignes.sort(key=_cle_tri)
    attribuer_designations(lignes)
    statut_global, texte, principal = construire_verdict(lignes, ld, le)
    res["statut_global"] = statut_global
    res["verdict"] = texte
    res["ecrasant_principal"] = principal
    res["inventaire"] = lignes

    # 12. Cohérence marché
    res["coherence_marche"] = coherence_marche(lignes, groupes_complets)
    return res


# ══════════════════════════════════════════════════════════════════════════
# PARTIE 17 — AFFICHAGE
# ══════════════════════════════════════════════════════════════════════════
LIMITES = """── LIMITES DU MODÈLE
- Poisson à buts indépendants : un seul couple de λ par match, pas d'xG,
  blessures, compositions, météo ni motivation.
- Ce modèle sous-estime en général les nuls. Sur les lignes entières (0.0, ±1.0, ±2.0),
  P_win est donc surestimé. Par défaut (égalité perdante, marché à 3 issues) l'EV y est
  biaisée à la hausse, sans terme de remboursement pour compenser : lecture optimiste.
- Avec --handicap-push-rembourse (option B), p_juste utilise le P_push du modèle,
  pas celui du marché, et l'effet net sur l'EV n'a pas de signe garanti.
- Marchés isolés : la marge n'est pas retirée, donc l'edge y est plutôt sous-estimé.
- Au-delà de cote 10, le modèle n'est pas jugé assez calibré pour exiger
  moins de 30 % d'EV ; ces marchés sont informatifs, non actionnables.
- Catégorie D (artefacts) exclue des désignations et du verdict."""


def afficher_match(res: Dict[str, Any], complet: bool) -> None:
    print("\n" + "═" * 100)
    print(f"Match {res['id']} — {res['nom_dom']} vs {res['nom_ext']}")
    if res["statut_global"] == "SKIP":
        print(f"  SKIP : {res['raison_skip']}")
        for ex in res["marches_exclus"]:
            print(f"  ✗ {ex['marche']} ({ex['cote']}) — {ex['raison']}")
        for a in res["avertissements_cotes"]:
            print(f"  ! {a}")
        return
    print(f"  λ dom {res['lambda_dom']:.3f} | λ ext {res['lambda_ext']:.3f} | "
          f"fenêtres : dom={res['n_matchs_dom']} ext={res['n_matchs_ext']}")
    if res["artefacts_match"]:
        print(f"  Artefacts de match : {', '.join(res['artefacts_match'])}")
    if res["avertissements_match"]:
        print(f"  Avertissements (hors catégorie D) : {', '.join(res['avertissements_match'])}")
    print(f"  {'Marché':<26}{'P':>8}{'p_juste':>9}{'Cote':>7}{'Edge':>9}{'EV':>9}{'Push':>8}  "
          f"{'Statut':<33}{'Cat':<4}Désignation")
    for l in res["inventaire"]:
        if not complet and not (l["is_value"] or l["proba_modele"] >= SEUIL_PROXIMITE_ECRASANT):
            continue
        print(f"  {l['marche']:<26}{_pct(l['proba_modele']):>8}{_pct(l['p_juste']):>9}"
              f"{l['cote']:>7.2f}{_spct(l['edge']):>9}{_spct(l['ev']):>9}{_pct(l['push']):>8}  "
              f"{l['statut']:<33}{(l['categorie'] or '-'):<4}{l['designation']}")
    print("  " + res["verdict"].replace("\n", "\n  "))
    c = res["coherence_marche"]
    if c:
        g = "n/a" if c["ecart_global"] is None else f"{c['ecart_global']:.3f}"
        print(f"  Cohérence marché : {c['verdict']} (écart global {g})")
    if res["marches_exclus"]:
        for ex in res["marches_exclus"]:
            print(f"  ✗ {ex['marche']} ({ex['cote']}) — {ex['raison']}")
    if res["non_reconnues"]:
        print(f"  Non reconnues : {', '.join(res['non_reconnues'])}")
    for a in res["avertissements_cotes"]:
        print(f"  ! {a}")


def afficher_synthese(resultats: List[Dict[str, Any]]) -> None:
    print("\n" + "═" * 100)
    print("SYNTHÈSE GLOBALE")
    statuts: Dict[str, int] = {}
    cats: Dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0}
    d_ev = d_arts = 0
    n_fenetre = n_asym = 0
    n_exclus_v1 = n_exclus_v2 = n_exclus_v3 = 0
    for r in resultats:
        statuts[r["statut_global"]] = statuts.get(r["statut_global"], 0) + 1
        if "Fenêtre d'analyse inconnue" in r["avertissements_match"]:
            n_fenetre += 1
        if r["biais_attaque_defense"]:
            n_asym += 1
        n_exclus_v1 += sum(1 for e in r["marches_exclus"] if "V1" in e["raison"])
        n_exclus_v2 += sum(1 for e in r["marches_exclus"] if "V2" in e["raison"])
        n_exclus_v3 += sum(1 for e in r["marches_exclus"] if "V3" in e["raison"])
        for l in r["inventaire"]:
            if l["categorie"]:
                cats[l["categorie"]] += 1
                if l["categorie"] == "D":
                    if l["ev"] > SEUIL_SUSPECT_EV:
                        d_ev += 1
                    else:
                        d_arts += 1
    print(f"  Matchs : {len(resultats)} | " + " | ".join(f"{k} : {v}" for k, v in sorted(statuts.items())))
    print("  Value bets par catégorie : " + " | ".join(f"{k} : {v}" for k, v in cats.items()))
    print(f"  Catégorie D : {d_ev} pour EV > 30 %, {d_arts} pour ≥ 2 artefacts")
    print(f"  V1 (marge groupe) : {n_exclus_v1} marché(s) exclus")
    print(f"  V2 (cohérence handicap) : {n_exclus_v2} marché(s) exclus")
    print(f"  V3 (plausibilité cote) : {n_exclus_v3} marché(s) exclus")
    print(f"  Avertissements : fenêtre inconnue sur {n_fenetre} match(s), "
          f"profil asymétrique sur {n_asym} match(s)")
    n_clamp = sum(1 for r in resultats if any(a.startswith("V6") for a in r["avertissements_match"]))
    n_v7 = sum(1 for r in resultats if any(a.startswith("V7") for a in r["avertissements_match"]))
    n_v8 = sum(1 for r in resultats if any("V8" in a for a in r["avertissements_cotes"]))
    n_v11 = sum(1 for r in resultats if "V11" in (r["raison_skip"] or ""))
    n_v12 = sum(1 for r in resultats if "V12" in (r["raison_skip"] or ""))
    print(f"  V6 λ clampé : {n_clamp} | V7 écart 1X2 > {SEUIL_COHERENCE_1X2:.2f} : {n_v7} | "
          f"V8 cotes périmées/illisibles : {n_v8} | V11 reportés : {n_v11} | V12 doublons : {n_v12}")
    print("\n" + LIMITES)


def _arrondi(obj: Any, nd: int = 6) -> Any:
    if isinstance(obj, float):
        return round(obj, nd)
    if isinstance(obj, dict):
        return {k: _arrondi(v, nd) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_arrondi(v, nd) for v in obj]
    return obj


# ══════════════════════════════════════════════════════════════════════════
# V12 — ANTI-DOUBLON INTER-RUN (opt-in)
# ══════════════════════════════════════════════════════════════════════════
def cle_doublon(match: Dict[str, Any], date_run: str) -> str:
    """Clé stable d'un match : date du run + équipes (les id sont réutilisés d'un fichier à l'autre)."""
    return f"{date_run}|{match.get('nom_dom')}|{match.get('nom_ext')}"


def charger_cache_doublon(chemin: str) -> Dict[str, str]:
    try:
        with open(chemin, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def est_doublon(cle: str, cache: Dict[str, str], maintenant: datetime) -> bool:
    ts = cache.get(cle)
    if not isinstance(ts, str):
        return False
    try:
        t = datetime.fromisoformat(ts)
    except ValueError:
        return False
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return 0 <= (maintenant - t).total_seconds() < FENETRE_DOUBLON_HEURES * 3600


def ecrire_cache_doublon(chemin: str, cache: Dict[str, str]) -> None:
    try:
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"Avertissement : cache anti-doublon non écrit ({e})", file=sys.stderr)


# ══════════════════════════════════════════════════════════════════════════
# AUTOTESTS
# ══════════════════════════════════════════════════════════════════════════
def autotest() -> int:
    ok = True

    def check(cond: bool, msg: str) -> None:
        nonlocal ok
        print(("  OK   " if cond else "  ÉCHEC ") + msg)
        ok = ok and cond

    print("Autotests V2.6.9")
    globals()["HANDICAP_ENTIER_REMBOURSE"] = False   # les tests supposent le défaut, quel que soit le flag CLI
    mat = construire_matrice(1.6, 1.1)
    check(abs(fsum(c for r in mat for c in r) - 1.0) < 1e-12, "somme de la matrice = 1")
    for H in LIGNES_HANDICAP:
        wd, pu, we = handicap_probas(mat, H)
        check(abs(wd + pu + we - 1.0) < 1e-12, f"invariant P_win_dom + P_push + P_win_ext = 1 (H={H})")
        if H != int(H):
            check(pu == 0.0, f"P_push = 0 sur la ligne .5 (H={H})")
        else:
            check(pu > 0.0, f"P_push > 0 sur la ligne entière (H={H})")
    check(seuil_ev_min(3.50) == 0.09 and seuil_ev_min(3.49) == 0.07 and seuil_ev_min(2.50) == 0.07
          and seuil_ev_min(2.49) == 0.06, "frontières de seuil_ev_min")
    check(parse_handicap_key("handicap_dom_-2_0") == ("dom", -2.0), "parse handicap_dom_-2_0")
    check(parse_handicap_key("handicap_ext_+1_5") == ("ext", 1.5), "parse handicap_ext_+1_5")
    check(parse_handicap_key("handicap_dom_0_0") == ("dom", 0.0), "parse handicap_dom_0_0")
    check(parse_handicap_key("handicap_nul_1_0") is None, "handicap_nul_X non reconnu")
    l1 = evaluer_ligne("x", 0.5299, 2.0, 0.5, 0.0)
    l2 = evaluer_ligne("x", 0.54, 2.0, 0.5, 0.0)
    check((not l1["is_value"]) and l2["is_value"], "frontière is_value (cote 2.00)")
    l3 = evaluer_ligne("h", 0.5, 2.0, 0.5, 0.2)
    check(abs(l3["ev"] - (0.5 * 2.0 - 1.0 + 0.2)) < 1e-12 and abs(l3["p_juste"] - 0.4) < 1e-12,
          "EV et p_juste avec push")

    # V1 — marge groupe (unitaire)
    r_ok = {"victoire": 2.0, "nul": 3.4, "defaite": 3.8}      # S ≈ 1.057
    g, rej = verifier_v1_marge_groupe(r_ok, {"1X2"}, 0)
    check("1X2" in g and not rej, "V1 : marge 1.057 acceptée")

    r_haut = {"victoire": 1.5, "nul": 2.5, "defaite": 2.5}    # S ≈ 1.467
    g, rej = verifier_v1_marge_groupe(r_haut, {"1X2"}, 0)
    check("1X2" not in g and "1X2" in rej, "V1 : marge 1.467 rejetée (> 1.20)")

    r_bas = {"victoire": 3.5, "nul": 4.0, "defaite": 4.0}     # S ≈ 0.786
    g, rej = verifier_v1_marge_groupe(r_bas, {"1X2"}, 0)
    check("1X2" not in g and "1X2" in rej, "V1 : marge 0.786 rejetée (< 1.00)")

    r_lim = {"victoire": 2.0, "nul": 3.0, "defaite": 3.0}     # S ≈ 1.167
    g, rej = verifier_v1_marge_groupe(r_lim, {"1X2"}, 0)
    check("1X2" in g, "V1 : marge 1.167 acceptée (proche borne haute)")

    # V2 — cohérence dom/ext sur demi-lignes (unitaire)
    cotes_v2_ok = {"handicap_dom_-1_5": 3.60, "handicap_ext_+1_5": 1.30}   # S ≈ 1.047
    hand_v2 = {"handicap_dom_-1_5": ("dom", -1.5), "handicap_ext_+1_5": ("ext", -1.5)}
    h, excl = verifier_v2_coherence_handicap(hand_v2, cotes_v2_ok, 0)
    check(len(h) == 2 and not excl, "V2 : paire cohérente (S ≈ 1.047) → conservée")

    cotes_v2_ko = {"handicap_dom_-1_5": 1.50, "handicap_ext_+1_5": 1.50}   # S ≈ 1.333
    h, excl = verifier_v2_coherence_handicap(hand_v2, cotes_v2_ko, 0)
    check(len(h) == 0 and len(excl) == 2, "V2 : paire incohérente (S ≈ 1.333) → rejetée")
    check(all("V2" in e["raison"] for e in excl), "V2 : raison tracée sur chaque exclusion")

    cotes_v2_ent = {"handicap_dom_-1_0": 1.50, "handicap_ext_+1_0": 1.50}
    hand_v2_ent = {"handicap_dom_-1_0": ("dom", -1.0), "handicap_ext_+1_0": ("ext", -1.0)}
    h, excl = verifier_v2_coherence_handicap(hand_v2_ent, cotes_v2_ent, 0)
    check(len(h) == 2 and not excl, "V2 : ligne entière ignorée (nécessiterait le nul)")

    cotes_v2_inc = {"handicap_dom_-1_5": 3.60}
    hand_v2_inc = {"handicap_dom_-1_5": ("dom", -1.5)}
    h, excl = verifier_v2_coherence_handicap(hand_v2_inc, cotes_v2_inc, 0)
    check(len(h) == 1 and not excl, "V2 : paire incomplète → aucune exclusion")

    # V3 — familles et fourchettes (unitaire)
    check(_famille_marche("victoire") == "1X2", "V3 famille : victoire → 1X2")
    check(_famille_marche("btts_oui") == "BTTS", "V3 famille : btts_oui → BTTS")
    check(_famille_marche("over_2_5") == "OU", "V3 famille : over_2_5 → OU")
    check(_famille_marche("buts_dom_over_0_5") == "BUTS_EQUIPE", "V3 famille : buts_dom_over_0_5 → BUTS_EQUIPE")
    check(_famille_marche("clean_sheet_dom") == "CLEAN_SHEET", "V3 famille : clean_sheet_dom → CLEAN_SHEET")
    check(_famille_marche("dc_1X") == "DC", "V3 famille : dc_1X → DC")
    check(_famille_marche("handicap_dom_-1_5") == "HANDICAP", "V3 famille : handicap_dom_-1_5 → HANDICAP")
    check(_famille_marche("inconnu_xyz") is None, "V3 famille : clé inconnue → None")

    # V3 — cote dans la fourchette : rien
    c_v3_ok = {"victoire": 2.0}
    r, ex, av = verifier_v3_plausibilite(c_v3_ok, {"victoire"}, 0)
    check(not r and not ex and not av, "V3 : victoire à 2.00 dans la fourchette → rien")

    # V3 — cote au-dessus du max : rejet + avertissement
    c_v3_haut = {"victoire": 50.0}   # max 1X2 = 30
    r, ex, av = verifier_v3_plausibilite(c_v3_haut, {"victoire"}, 0)
    check(r == {"victoire"} and len(ex) == 1 and len(av) == 1,
          "V3 : victoire à 50.00 (> 30) → rejet + avertissement")
    check("V3" in ex[0]["raison"] and "V3" in av[0], "V3 : raison et avertissement mentionnent V3")

    # V3 — cote sous le min (famille OU) : rejet
    c_v3_min = {"over_0_5": 1.005}   # min OU = 1.01, passe filtre (>1.0)
    r, ex, av = verifier_v3_plausibilite(c_v3_min, {"over_0_5"}, 0)
    check(r == {"over_0_5"}, "V3 : over_0_5 à 1.005 (< 1.01) → rejet")

    # V3 — handicap dans la fourchette malgré une cote élevée
    c_v3_hand = {"handicap_dom_-2_0": 50.0}   # max HANDICAP = 100
    r, ex, av = verifier_v3_plausibilite(c_v3_hand, {"handicap_dom_-2_0"}, 0)
    check(not r, "V3 : handicap à 50.00 (< 100) → conservé")

    # V3 — cote sur un marché non actif : ignorée
    c_v3_inactif = {"victoire": 50.0}
    r, ex, av = verifier_v3_plausibilite(c_v3_inactif, set(), 0)
    check(not r and not ex and not av, "V3 : marché non actif → ignoré")

    # V1 — test d'intégration : match normal, pas d'exclusion
    m = {"id": 0, "nom_dom": "A", "nom_ext": "B",
         "equipe_dom": {"nom": "A", "buts_marques_moy": 1.8, "buts_encaisses_moy": 1.0},
         "equipe_ext": {"nom": "B", "buts_marques_moy": 1.2, "buts_encaisses_moy": 1.4},
         "cotes": {"victoire": 2.0, "nul": 3.4, "defaite": 3.8, "btts_oui": 1.85, "btts_non": 1.95,
                   "handicap_dom_-1_5": 3.6, "handicap_ext_+1_5": 1.3, "handicap_dom_-1_0": 2.9,
                   "handicap_ext_+1_0": 1.4, "handicap_nul_1_0": 4.0, "cote_bidon": "x"},
         "meta": {"fiabilite": "OK"}}
    r = analyser_match(m)
    par = {l["marche"]: l for l in r["inventaire"]}
    check(abs(par["handicap_dom_-1_5"]["proba_modele"] + par["handicap_ext_+1_5"]["proba_modele"] - 1.0) < 1e-12,
          "handicap_dom_-1_5 + handicap_ext_+1_5 = 1")
    check(par["handicap_dom_-1_0"]["push"] > 0 and par["handicap_ext_+1_0"]["push"] == par["handicap_dom_-1_0"]["push"],
          "push identique des deux côtés d'une ligne entière")
    check("handicap_nul_1_0" in r["non_reconnues"], "handicap_nul_X → non_reconnues")
    check(any("cote_bidon" in a for a in r["avertissements_cotes"]), "cote non numérique rejetée (marché seul)")
    check(r["statut_global"] in ("ECRASANT_JOUABLE", "COMPROMIS", "AUCUN"), "match complet analysé (pas de SKIP)")
    check(r["n_matchs_dom"] is None and "Fenêtre d'analyse inconnue" in r["avertissements_match"]
          and r["artefacts_match"] == [], "R4 : avertissement (pas artefact) sans matchs_recents")
    check(r["marches_exclus"] == [], "V1/V2/V3 : données cohérentes → aucune exclusion")

    # V1 — test d'intégration : groupe rejeté, le match continue
    m2 = {"id": 1, "nom_dom": "C", "nom_ext": "D",
          "equipe_dom": {"nom": "C", "buts_marques_moy": 1.0, "buts_encaisses_moy": 1.0},
          "equipe_ext": {"nom": "D", "buts_marques_moy": 1.0, "buts_encaisses_moy": 1.0},
          "cotes": {"victoire": 1.5, "nul": 2.5, "defaite": 2.5,   # S ≈ 1.467 → rejet V1
                    "btts_oui": 1.85, "btts_non": 1.95,
                    "handicap_dom_-1_5": 3.6, "handicap_ext_+1_5": 1.3},
          "meta": {"fiabilite": "OK"}}
    r2 = analyser_match(m2)
    excl_marches = {e["marche"] for e in r2["marches_exclus"]}
    check({"victoire", "nul", "defaite"} <= excl_marches, "V1 : groupe 1X2 surcoté exclu et tracé")
    check(all("V1" in e["raison"] for e in r2["marches_exclus"]), "V1 : raison tracée sur chaque exclusion")
    check(not any(l["marche"] in ("victoire", "nul", "defaite") for l in r2["inventaire"]),
          "V1 : marchés exclus absents de l'inventaire")
    check(r2["statut_global"] != "SKIP", "V1 + seuil : 4 marchés restants → analyse maintenue")

    # V1 — test d'intégration : groupe rejeté laisse trop peu de marchés → SKIP
    m3 = {"id": 2, "nom_dom": "E", "nom_ext": "F",
          "equipe_dom": {"nom": "E", "buts_marques_moy": 1.0, "buts_encaisses_moy": 1.0},
          "equipe_ext": {"nom": "F", "buts_marques_moy": 1.0, "buts_encaisses_moy": 1.0},
          "cotes": {"victoire": 1.5, "nul": 2.5, "defaite": 2.5},   # seul groupe, rejeté V1
          "meta": {"fiabilite": "OK"}}
    r3 = analyser_match(m3)
    check(r3["statut_global"] == "SKIP", "V1 + seuil : groupe unique rejeté → SKIP")
    check("V1/V2/V3 ont laissé" in (r3["raison_skip"] or ""), "V1 + seuil : raison tracée avec mention V1/V2/V3")

    # V2 — test d'intégration : paire de handicap incohérente
    m4 = {"id": 3, "nom_dom": "G", "nom_ext": "H",
          "equipe_dom": {"nom": "G", "buts_marques_moy": 1.5, "buts_encaisses_moy": 1.0},
          "equipe_ext": {"nom": "H", "buts_marques_moy": 1.0, "buts_encaisses_moy": 1.5},
          "cotes": {"victoire": 2.0, "nul": 3.4, "defaite": 3.8,
                    "btts_oui": 1.85, "btts_non": 1.95,
                    "handicap_dom_-1_5": 1.50, "handicap_ext_+1_5": 1.50},   # S ≈ 1.333
          "meta": {"fiabilite": "OK"}}
    r4 = analyser_match(m4)
    excl4 = {e["marche"] for e in r4["marches_exclus"]}
    check({"handicap_dom_-1_5", "handicap_ext_+1_5"} <= excl4,
          "V2 : paire incohérente exclue et tracée")
    check(not any(l["marche"] in ("handicap_dom_-1_5", "handicap_ext_+1_5") for l in r4["inventaire"]),
          "V2 : marchés exclus absents de l'inventaire")

    # V3 — test d'intégration : cote cassée → rejet + avertissement
    m5 = {"id": 4, "nom_dom": "I", "nom_ext": "J",
          "equipe_dom": {"nom": "I", "buts_marques_moy": 1.5, "buts_encaisses_moy": 1.0},
          "equipe_ext": {"nom": "J", "buts_marques_moy": 1.0, "buts_encaisses_moy": 1.5},
          "cotes": {"victoire": 2.0, "nul": 3.4, "defaite": 3.8,
                    "clean_sheet_dom": 50.0,                          # V3 : hors [1.05, 30] (marché isolé, V1 ne le voit pas)
                    "btts_oui": 1.85, "btts_non": 1.95,
                    "handicap_dom_-1_5": 3.6, "handicap_ext_+1_5": 1.3},
          "meta": {"fiabilite": "OK"}}
    r5 = analyser_match(m5)
    excl5 = {e["marche"] for e in r5["marches_exclus"]}
    check("clean_sheet_dom" in excl5, "V3 : clean_sheet_dom à 50.00 exclu et tracé")
    check(any("V3" in e["raison"] for e in r5["marches_exclus"]), "V3 : raison tracée sur exclusion")
    check(any("V3" in a for a in r5["avertissements_cotes"]), "V3 : avertissement émis")
    check(not any(l["marche"] == "clean_sheet_dom" for l in r5["inventaire"]),
          "V3 : marché exclu absent de l'inventaire")

    # V4 — fiabilité (unitaire, fonction pure)
    check(verifier_v4_fiabilite({}) == (None, None), "V4 : pas de meta → (None, None)")
    check(verifier_v4_fiabilite({"meta": None}) == (None, None), "V4 : meta None → (None, None)")
    check(verifier_v4_fiabilite({"meta": {"fiabilite": "FALLBACK"}}) == ("FALLBACK", "meta"),
          "V4 : meta FALLBACK → (FALLBACK, meta)")
    check(verifier_v4_fiabilite({"meta": {"fiabilite": " fallback "}}) == ("FALLBACK", "meta"),
          "V4 : valeur normalisée (casse, espaces)")
    check(verifier_v4_fiabilite({"meta": {"fiabilite": "OK"}}) == ("OK", "meta"), "V4 : meta OK conservé")
    check(verifier_v4_fiabilite({"meta": {"fiabilite": 3}}) == (None, None), "V4 : valeur non textuelle ignorée")
    check(verifier_v4_fiabilite({"meta": "x"}) == (None, None), "V4 : meta non dict ignoré")

    # V4 — matchs_joues (unitaire)
    base = {"nom": "Z", "buts_marques_moy": 1.0, "buts_encaisses_moy": 1.0}
    check(preparer_equipe({**base, "matchs_joues": 12})[2:] == (12, []), "matchs_joues = 12 → n = 12")
    check(preparer_equipe({**base, "matchs_joues": 12.0})[2] == 12, "matchs_joues = 12.0 → n = 12")
    check(preparer_equipe(base)[2:] == (None, []), "matchs_joues absent → n = None, sans avertissement")
    for bad in (0, -3, 2.5, "12", True):
        n_b, av_b = preparer_equipe({**base, "matchs_joues": bad})[2:]
        check(n_b is None and len(av_b) == 1 and "matchs_joues invalide" in av_b[0],
              f"matchs_joues = {bad!r} → ignoré + avertissement")
    rec = {"nom": "Z", "matchs_recents": [[1, 0], [2, 2], [0, 1]], "matchs_joues": 99}
    check(preparer_equipe(rec)[2:] == (3, []), "matchs_recents prime sur matchs_joues, sans avertissement")
    rec_bad = {"nom": "Z", "matchs_recents": [[1, 0]], "matchs_joues": 0}
    check(preparer_equipe(rec_bad)[2:] == (1, []), "matchs_recents + matchs_joues invalide → pas d'avertissement")

    # V4 — intégration
    def _m(mid, dom_extra=None, ext_extra=None, meta=None):
        return {"id": mid, "nom_dom": "A", "nom_ext": "B",
                "equipe_dom": {"nom": "A", "buts_marques_moy": 1.8, "buts_encaisses_moy": 1.0, **(dom_extra or {})},
                "equipe_ext": {"nom": "B", "buts_marques_moy": 1.2, "buts_encaisses_moy": 1.4, **(ext_extra or {})},
                "cotes": {"victoire": 2.0, "nul": 3.4, "defaite": 3.8, "btts_oui": 1.85, "btts_non": 1.95},
                **({"meta": meta} if meta is not None else {})}
    rj = analyser_match(_m(10, {"matchs_joues": 12}, {"matchs_joues": 12}))
    check(rj["n_matchs_dom"] == 12 and rj["n_matchs_ext"] == 12
          and rj["avertissements_match"] == [] and rj["artefacts_match"] == [],
          "V4 : matchs_joues = 12 des deux côtés → plus d'avertissement de fenêtre")
    rc = analyser_match(_m(11, {"matchs_joues": 3}, {"matchs_joues": 12}))
    check(rc["avertissements_match"] == ["Fenêtre d'analyse trop courte"], "V4 : matchs_joues = 3 → R4 fenêtre trop courte")
    ri = analyser_match(_m(12, {"matchs_joues": 0}, {"matchs_joues": 12}))
    check(any("matchs_joues invalide" in a for a in ri["avertissements_match"])
          and "Fenêtre d'analyse inconnue" in ri["avertissements_match"],
          "V4 : matchs_joues = 0 → avertissement d'invalidité + fenêtre inconnue")
    rf = analyser_match(_m(13, meta={"fiabilite": "FALLBACK"}))
    check(rf["artefacts_match"] == ["Données issues du classement uniquement"]
          and rf["fiabilite"] == "FALLBACK" and rf["fiabilite_origine"] == "meta",
          "V4 : meta FALLBACK → R3 + fiabilité tracée")
    ra = analyser_match(_m(14))
    check(ra["artefacts_match"] == [] and ra["fiabilite"] is None,
          "V4 : sans meta ni matchs_recents → pas de FALLBACK inféré")
    rl = analyser_match(_m(15, meta={"fiabilite": "fallback"}))
    check(rl["artefacts_match"] == ["Données issues du classement uniquement"], "V4 : 'fallback' minuscule → R3")
    check(all("V4" not in a for a in rf["avertissements_match"]),
          "V4 : override manuel → aucun avertissement V4 (l'utilisateur le sait déjà)")

    # V5 — bornes des moyennes (unitaire)
    base5 = {"nom": "Z"}
    for bad_bas in (-0.1, -5):
        try:
            preparer_equipe({**base5, "buts_marques_moy": bad_bas, "buts_encaisses_moy": 1.0})
            check(False, f"V5 : buts_marques_moy = {bad_bas} → aurait dû lever")
        except ValueError as e:
            check("V5" in str(e) and "< 0" in str(e), f"V5 : buts_marques_moy = {bad_bas} → rejet tracé V5")
    a5, d5, n5, av5 = preparer_equipe({**base5, "buts_marques_moy": 10.0, "buts_encaisses_moy": 10.0})
    check((a5, d5, n5, av5) == (10.0, 10.0, None, []), "V5 : moyenne = 10.0 → acceptée (borne inclusive)")
    a5, d5, _, _ = preparer_equipe({**base5, "buts_marques_moy": 0, "buts_encaisses_moy": 0})
    check((a5, d5) == (0.0, 0.0), "V5 : moyenne = 0 → acceptée (borne inclusive)")
    for bad_haut in (10.01, 15, 100):
        try:
            preparer_equipe({**base5, "buts_marques_moy": bad_haut, "buts_encaisses_moy": 1.0})
            check(False, f"V5 : buts_marques_moy = {bad_haut} → aurait dû lever")
        except ValueError as e:
            check("V5" in str(e) and "> 10.0" in str(e), f"V5 : buts_marques_moy = {bad_haut} → rejet tracé V5")
    try:
        preparer_equipe({**base5, "buts_marques_moy": 1.0, "buts_encaisses_moy": 12.5})
        check(False, "V5 : buts_encaisses_moy = 12.5 → aurait dû lever")
    except ValueError as e:
        check("V5" in str(e) and "buts_encaisses_moy" in str(e), "V5 : buts_encaisses_moy = 12.5 → rejet tracé V5")
    try:
        preparer_equipe({**base5, "matchs_recents": [[12, 0], [11, 1]]})
        check(False, "V5 : matchs_recents à moyenne 11.5 → aurait dû lever")
    except ValueError as e:
        check("V5" in str(e) and "buts_marques_moy" in str(e), "V5 : moyennes calculées sur matchs_recents aussi bornées")
    # V5 — intégration : SKIP du match
    m_v5 = {"id": 20, "nom_dom": "A", "nom_ext": "B",
            "equipe_dom": {"nom": "A", "buts_marques_moy": 12.0, "buts_encaisses_moy": 1.0},
            "equipe_ext": {"nom": "B", "buts_marques_moy": 1.0, "buts_encaisses_moy": 1.0},
            "cotes": {"victoire": 2.0, "nul": 3.4, "defaite": 3.8, "btts_oui": 1.85, "btts_non": 1.95}}
    r_v5 = analyser_match(m_v5)
    check(r_v5["statut_global"] == "SKIP" and "V5" in (r_v5["raison_skip"] or ""),
          "V5 : moyenne hors bornes → SKIP match avec raison V5")

    # V6 — clamp λ tracé
    ld6, le6, cl6 = calcul_lambdas_trace(1.5, 1.0, 1.0, 1.5)
    check(not cl6["dom"]["clamp_applique"] and not cl6["ext"]["clamp_applique"]
          and abs(ld6 - 1.5) < 1e-12 and abs(le6 - 1.0) < 1e-12, "V6 : entrée normale → aucun clamp")
    ld6, le6, cl6 = calcul_lambdas_trace(20.0, 20.0, 20.0, 20.0)
    check(ld6 == LAMBDA_MAX and le6 == LAMBDA_MAX and cl6["dom"]["clamp_applique"] and cl6["ext"]["clamp_applique"]
          and cl6["dom"]["brut"] == 20.0, "V6 : 20/20 → clamp haut des deux côtés, brut conservé")
    ld6, le6, cl6 = calcul_lambdas_trace(0.0, 0.0, 0.0, 0.0)
    check(ld6 == LAMBDA_MIN and le6 == LAMBDA_MIN and cl6["dom"]["clamp_applique"], "V6 : entrée nulle → clamp bas")
    ld6, le6, cl6 = calcul_lambdas_trace(12.0, 1.0, 1.0, 12.0)   # dom brut 12, ext brut 1
    check(cl6["dom"]["clamp_applique"] and not cl6["ext"]["clamp_applique"], "V6 : clamp d'un seul côté")
    check(calcul_lambdas(1.5, 1.0, 1.0, 1.5) == (1.5, 1.0), "V6 : calcul_lambdas (compat) inchangé")
    m6 = {"id": 30, "nom_dom": "A", "nom_ext": "B",
          "equipe_dom": {"nom": "A", "buts_marques_moy": 0.0, "buts_encaisses_moy": 1.0},
          "equipe_ext": {"nom": "B", "buts_marques_moy": 1.0, "buts_encaisses_moy": 0.0},
          "cotes": {"victoire": 2.0, "nul": 3.4, "defaite": 3.8, "btts_oui": 1.85, "btts_non": 1.95}}
    r6 = analyser_match(m6)   # λ dom brut 0.0 → clamp bas (le clamp haut est inatteignable après V5)
    check(any(a.startswith("V6") for a in r6["avertissements_match"]) and r6["clamps_lambda"]["dom"]["clamp_applique"]
          and not r6["clamps_lambda"]["ext"]["clamp_applique"],
          "V6 : intégration → avertissement + clamps_lambda dans le résultat")

    # V7 — cohérence λ / 1X2
    pr7 = probas_standard(construire_matrice(1.6, 1.1))
    marge = 1.05
    cotes_ok = {k: 1.0 / (pr7[k] * marge) for k in ("victoire", "nul", "defaite")}
    e7, av7 = verifier_v7_coherence_1x2(pr7, cotes_ok, {"1X2"})
    check(e7 is not None and e7 < SEUIL_COHERENCE_1X2 and av7 == [], "V7 : cotes alignées sur le modèle → pas d'avertissement")
    cotes_ko = {"victoire": 5.0, "nul": 3.4, "defaite": 1.6}   # marché à l'opposé du modèle (λ dom > λ ext)
    e7, av7 = verifier_v7_coherence_1x2(pr7, cotes_ko, {"1X2"})
    check(e7 > SEUIL_COHERENCE_1X2 and len(av7) == 1 and av7[0].startswith("V7"), "V7 : marché opposé au modèle → avertissement")
    e7, av7 = verifier_v7_coherence_1x2(pr7, cotes_ko, set())
    check(e7 is None and av7 == [], "V7 : 1X2 incomplet → pas de calcul")
    m7 = {"id": 31, "nom_dom": "A", "nom_ext": "B",
          "equipe_dom": {"nom": "A", "buts_marques_moy": 2.5, "buts_encaisses_moy": 0.8},
          "equipe_ext": {"nom": "B", "buts_marques_moy": 0.8, "buts_encaisses_moy": 2.0},
          "cotes": {"victoire": 5.0, "nul": 3.4, "defaite": 1.7, "btts_oui": 1.85, "btts_non": 1.95}}
    r7 = analyser_match(m7)
    check(r7["coherence_1x2_modele"] is not None and any(a.startswith("V7") for a in r7["avertissements_match"])
          and r7["statut_global"] != "SKIP", "V7 : intégration → avertissement, match non rejeté")

    # V8 — fraîcheur des cotes
    t0 = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
    check(verifier_v8_fraicheur({}, t0, 0) == [], "V8 : champ absent → silencieux")
    check(verifier_v8_fraicheur({"cotes_prises_le": "2026-09-20T10:00:00+00:00"}, t0, 0) == [], "V8 : cotes de 2 h → rien")
    a8 = verifier_v8_fraicheur({"cotes_prises_le": "2026-09-19T06:00:00+00:00"}, t0, 0)
    check(len(a8) == 1 and "V8" in a8[0] and "30.0 h" in a8[0], "V8 : cotes de 30 h → avertissement")
    check(len(verifier_v8_fraicheur({"cotes_prises_le": "hier"}, t0, 0)) == 1, "V8 : horodatage illisible → avertissement")
    check(len(verifier_v8_fraicheur({"cotes_prises_le": 12345}, t0, 0)) == 1, "V8 : horodatage non textuel → avertissement")
    check(len(verifier_v8_fraicheur({"cotes_prises_le": "2026-09-20T15:00:00+00:00"}, t0, 0)) == 1, "V8 : horodatage futur → avertissement")
    check(verifier_v8_fraicheur({"cotes_prises_le": "2026-09-20T10:00:00"}, t0, 0) == [], "V8 : sans fuseau → lu comme UTC")
    m8 = {**m, "id": 32, "cotes_prises_le": "2026-09-01T00:00:00+00:00"}
    r8 = analyser_match(m8, "", t0)
    check(any("V8" in a for a in r8["avertissements_cotes"]), "V8 : intégration → avertissement dans avertissements_cotes")

    # V11 — match reporté / annulé
    check(verifier_v11_statut_match({"statut": "reporte"}, "2026-09-20", 0)[0] is False, "V11 : statut reporte → inactif")
    check(verifier_v11_statut_match({"statut": " Reporté "}, "2026-09-20", 0)[0] is False, "V11 : statut ' Reporté ' (casse, accent) → inactif")
    check(verifier_v11_statut_match({"statut": "annulé"}, "", 0)[0] is False, "V11 : statut annulé → inactif")
    check(verifier_v11_statut_match({"date_match": "2026-09-21"}, "2026-09-20", 0)[0] is False, "V11 : date différente → inactif")
    check(verifier_v11_statut_match({"date_match": "2026-09-20"}, "2026-09-20", 0)[0] is True, "V11 : même date → actif")
    check(verifier_v11_statut_match({"date_match": "2026-09-21"}, "", 0)[0] is True, "V11 : date du run inconnue → pas de contrôle")
    check(verifier_v11_statut_match({"statut": "programme"}, "2026-09-20", 0)[0] is True, "V11 : statut normal → actif")
    check(verifier_v11_statut_match({}, "2026-09-20", 0) == (True, None), "V11 : aucun champ → actif")
    r11 = analyser_match({**m, "id": 33, "statut": "reporte"}, "2026-09-20", t0)
    check(r11["statut_global"] == "SKIP" and "V11" in (r11["raison_skip"] or ""), "V11 : intégration → SKIP avec raison V11")

    # V12 — anti-doublon
    import os, tempfile
    now12 = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
    check(est_doublon("k", {}, now12) is False, "V12 : cache vide → pas de doublon")
    check(est_doublon("k", {"k": "2026-09-20T11:00:00+00:00"}, now12) is True, "V12 : vu il y a 1 h → doublon")
    check(est_doublon("k", {"k": "2026-09-20T09:00:00+00:00"}, now12) is False, "V12 : vu il y a 3 h → pas doublon")
    check(est_doublon("k", {"k": "n'importe quoi"}, now12) is False, "V12 : horodatage illisible → pas doublon")
    check(est_doublon("k", {"k": "2026-09-20T13:00:00+00:00"}, now12) is False, "V12 : horodatage futur → pas doublon")
    check(cle_doublon({"nom_dom": "A", "nom_ext": "B"}, "2026-09-20") != cle_doublon({"nom_dom": "A", "nom_ext": "B"}, "2026-09-21"),
          "V12 : la clé dépend de la date (les id sont réutilisés d'un fichier à l'autre)")
    with tempfile.TemporaryDirectory() as tmp:
        chemin = os.path.join(tmp, "c.json")
        check(charger_cache_doublon(chemin) == {}, "V12 : fichier de cache absent → {}")
        ecrire_cache_doublon(chemin, {"k": "2026-09-20T11:00:00+00:00"})
        check(charger_cache_doublon(chemin) == {"k": "2026-09-20T11:00:00+00:00"}, "V12 : écriture/relecture du cache")
        with open(chemin, "w", encoding="utf-8") as f:
            f.write("{pas du json")
        check(charger_cache_doublon(chemin) == {}, "V12 : cache corrompu → {}")

    # V10 — normalisation
    check(abs(masse_avant_normalisation(1.6, 1.1) - 1.0) < 1e-9, "V10 : masse ≈ 1 pour λ usuels")
    check(verifier_v10_normalisation(1.6, 1.1) == [] and verifier_v10_normalisation(3.25, 1.5) == [],
          "V10 : λ usuels (≤ 3.3) → aucun avertissement")
    av10 = verifier_v10_normalisation(10.0, 10.0)
    check(len(av10) == 1 and av10[0].startswith("V10"), "V10 : λ = 10/10 → avertissement (masse tronquée)")
    check(masse_avant_normalisation(10.0, 10.0) < 1.0 - TOLERANCE_NORMALISATION, "V10 : masse λ=10/10 nettement < 1")
    m10 = {"id": 40, "nom_dom": "A", "nom_ext": "B",
           "equipe_dom": {"nom": "A", "buts_marques_moy": 10.0, "buts_encaisses_moy": 10.0},
           "equipe_ext": {"nom": "B", "buts_marques_moy": 10.0, "buts_encaisses_moy": 10.0},
           "cotes": {"victoire": 2.0, "nul": 3.4, "defaite": 3.8, "btts_oui": 1.85, "btts_non": 1.95}}
    r10 = analyser_match(m10)
    check(any(a.startswith("V10") for a in r10["avertissements_match"]) and r10["statut_global"] != "SKIP",
          "V10 : intégration → avertissement, match non rejeté")

    # Option 2 — handicaps à ligne entière : l'égalité perd (3 issues)
    lp = evaluer_ligne("h", 0.5, 2.0, 0.5, 0.2, remboursement_push=False)
    check(abs(lp["ev"] - 0.0) < 1e-12 and abs(lp["p_juste"] - 0.5) < 1e-12 and lp["push"] == 0.2,
          "Option 2 : EV = p·cote − 1, p_juste = 1/cote, push conservé pour l'affichage")
    lr = evaluer_ligne("h", 0.5, 2.0, 0.5, 0.2, remboursement_push=True)
    check(abs(lr["ev"] - 0.2) < 1e-12 and abs(lr["p_juste"] - 0.4) < 1e-12,
          "Option B (remboursement) : EV + P_push et p_juste ajusté (inchangé)")
    check(evaluer_ligne("h", 0.5, 2.0, 0.5, 0.0, remboursement_push=False)["ev"]
          == evaluer_ligne("h", 0.5, 2.0, 0.5, 0.0, remboursement_push=True)["ev"],
          "Ligne .5 (push = 0) : identique dans les deux modes")
    check(HANDICAP_ENTIER_REMBOURSE is False, "Défaut : l'égalité sur la ligne perd")
    m_h = {"id": 50, "nom_dom": "A", "nom_ext": "B",
           "equipe_dom": {"nom": "A", "buts_marques_moy": 1.8, "buts_encaisses_moy": 1.0},
           "equipe_ext": {"nom": "B", "buts_marques_moy": 1.2, "buts_encaisses_moy": 1.4},
           "cotes": {"victoire": 2.0, "nul": 3.4, "defaite": 3.8, "btts_oui": 1.85, "btts_non": 1.95,
                     "handicap_dom_-1_0": 2.9, "handicap_ext_+1_0": 1.4,
                     "handicap_dom_-1_5": 3.6, "handicap_ext_+1_5": 1.3}}
    rh = analyser_match(m_h)
    ph = {l["marche"]: l for l in rh["inventaire"]}
    li = ph["handicap_dom_-1_0"]
    check(abs(li["ev"] - (li["proba_modele"] * 2.9 - 1.0)) < 1e-12 and abs(li["p_juste"] - 1 / 2.9) < 1e-12
          and li["push"] > 0, "Option 2 : intégration, ligne entière sans remboursement")
    lh = ph["handicap_dom_-1_5"]
    check(abs(lh["ev"] - (lh["proba_modele"] * 3.6 - 1.0)) < 1e-12 and lh["push"] == 0.0,
          "Option 2 : intégration, ligne .5 inchangée")
    globals()["HANDICAP_ENTIER_REMBOURSE"] = True
    try:
        rb = analyser_match(m_h)
        pb = {l["marche"]: l for l in rb["inventaire"]}["handicap_dom_-1_0"]
        check(abs(pb["ev"] - (pb["proba_modele"] * 2.9 - 1.0 + pb["push"])) < 1e-12,
              "Option B via HANDICAP_ENTIER_REMBOURSE = True : EV avec remboursement")
    finally:
        globals()["HANDICAP_ENTIER_REMBOURSE"] = False

    print("\nRésultat :", "TOUS LES TESTS PASSENT" if ok else "AU MOINS UN TEST ÉCHOUE")
    return 0 if ok else 1


# ══════════════════════════════════════════════════════════════════════════
# CHARGEMENT DES DONNÉES
# ══════════════════════════════════════════════════════════════════════════
def charger_matchs(chemin: str) -> List[Dict[str, Any]]:
    """JSON (liste ou {"matchs": [...]}) ou fichier Python/texte contenant `MATCHS = [...]`.

    Le fichier Python n'est JAMAIS exécuté : la valeur de MATCHS est lue avec ast.literal_eval.
    """
    with open(chemin, encoding="utf-8") as f:
        contenu = f.read()
    try:
        data = json.loads(contenu)
        return data.get("matchs", []) if isinstance(data, dict) else data
    except json.JSONDecodeError:
        pass
    arbre = ast.parse(contenu)
    for noeud in arbre.body:
        if (isinstance(noeud, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "MATCHS" for t in noeud.targets)):
            return ast.literal_eval(noeud.value)
    raise ValueError("Aucune variable MATCHS trouvée dans le fichier")


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════
def main() -> int:
    ap = argparse.ArgumentParser(description="Moteur de value bets V2.6.9 (Phase 1, V1-V12)")
    ap.add_argument("fichier", nargs="?", help="JSON de matchs")
    ap.add_argument("--sortie", help="Chemin du rapport JSON (défaut : rapport_<date>.json)")
    ap.add_argument("--date", default=date.today().isoformat(), help="Date du rapport (YYYY-MM-DD)")
    ap.add_argument("--complet", action="store_true", help="Afficher tout l'inventaire")
    ap.add_argument("--autotest", action="store_true", help="Lancer les autotests")
    ap.add_argument("--cache", action="store_true",
                    help=f"V12 : ignore un match déjà traité il y a moins de {FENETRE_DOUBLON_HEURES} h "
                         f"(cache {CACHE_DOUBLON}, désactivé par défaut)")
    ap.add_argument("--handicap-push-rembourse", action="store_true",
                    help="Option B de la spec 2.6.2 : push remboursé sur les lignes entières "
                         "(handicap asiatique). Défaut : l'égalité sur la ligne perd (3 issues).")
    ap.add_argument("--lignes-etendues", action="store_true",
                    help="Hors spec V2.6.2 : accepte aussi les handicaps ±2.5 et ±3.0")
    args = ap.parse_args()
    global LIGNES_ACTIVES, HANDICAP_ENTIER_REMBOURSE
    if args.lignes_etendues:
        LIGNES_ACTIVES = LIGNES_HANDICAP_ETENDUES
    if args.handicap_push_rembourse:
        HANDICAP_ENTIER_REMBOURSE = True

    if args.autotest:
        return autotest()
    if not args.fichier:
        ap.error("fichier de matchs requis (ou --autotest)")

    matchs = charger_matchs(args.fichier)

    maintenant = datetime.now(timezone.utc)
    cache = charger_cache_doublon(CACHE_DOUBLON) if args.cache else {}

    resultats: List[Dict[str, Any]] = []
    for match in matchs:
        cle = cle_doublon(match, args.date)
        if args.cache and est_doublon(cle, cache, maintenant):
            res = resultat_vide(match)
            res["raison_skip"] = (f"[Match {match.get('id')}] V12 : déjà traité il y a moins de "
                                  f"{FENETRE_DOUBLON_HEURES} h")
            resultats.append(res)
            afficher_match(res, args.complet)
            continue  # l'horodatage n'est pas rafraîchi : la fenêtre ne glisse pas
        try:
            res = analyser_match(match, args.date, maintenant)
        except Exception as e:  # une erreur inattendue ne doit pas arrêter les autres matchs
            traceback.print_exc(file=sys.stderr)
            res = resultat_vide(match)
            res["raison_skip"] = f"Erreur inattendue : {e!r}"
        resultats.append(res)
        afficher_match(res, args.complet)
        if args.cache:
            cache[cle] = maintenant.isoformat()

    if args.cache:
        ecrire_cache_doublon(CACHE_DOUBLON, cache)

    afficher_synthese(resultats)

    sortie = args.sortie or f"rapport_{args.date}.json"
    rapport = {"date": args.date, "version_moteur": "2.6.9", "matchs": _arrondi(resultats)}
    with open(sortie, "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2)
    print(f"\nRapport JSON écrit dans {sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())