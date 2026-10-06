# -*- coding: utf-8 -*-
"""
moteur_v2_6_10.noyau — cœur méthodologique du moteur de value bets, désormais PROPRIÉTÉ de la v2.6.10.

Ce module est le transfert, sans changement de règle, du cœur de `moteur_v2_6_9.py` (spec V2.6.2 figée + vérificateurs
V1-V8, V10, V11) : validations, Poisson, marchés, value (edge, EV, seuils), statuts, artefacts R1-R3, catégories A-D,
désignations, verdict, cohérence marché, schéma du résultat. Il ne dépend d'AUCUN autre module du dépôt.

Volontairement absents (ils n'appartiennent pas au calcul) : affichage console, rapport JSON, cache anti-doublon V12
(outil en ligne de commande), autotests (voir `moteur_v2_6_10.autotest`).

Handicaps à ligne entière (H = 0, ±1, ±2) : marché à trois issues (source BetPawa « Handicap à 3 choix »). L'égalité sur
la ligne PERD les paris dom et ext : EV = P_win × cote − 1, p_juste = 1/cote. Option B (push remboursé) via
`HANDICAP_ENTIER_REMBOURSE = True`.

Ordre des opérations (figé) :
    DONNÉES → VALIDATION → VÉRIFICATEURS → CALCUL → VALUE → STATUT → ARTEFACTS
    → CATÉGORIE → DÉSIGNATION → VERDICT
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import exp, factorial, fsum
from typing import Any, Dict, List, Optional, Set, Tuple

# ══════════════════════════════════════════════════════════════════════════
# CONSTANTES
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
LIGNES_HANDICAP_ETENDUES = (-3.0, -2.5) + LIGNES_HANDICAP + (2.5, 3.0)
LIGNES_ACTIVES = LIGNES_HANDICAP

# Bornes des catégories
CAT_EV_MAX_AB = 0.20
CAT_P_MIN_A = 0.45
CAT_P_MIN_B = 0.30

# V1, V2
MARGE_GROUPE_MIN = 1.00
MARGE_GROUPE_MAX = 1.20

# V5 — bornes de plausibilité des moyennes de buts (par match, par équipe), inclusives.
MOYENNE_BUTS_MAX = 10.0

# V10 — masse de Poisson perdue à la troncature au-delà de laquelle on avertit.
TOLERANCE_NORMALISATION = 1e-6

# Handicaps à ligne entière : False = l'égalité perd (3 issues, défaut) ; True = push remboursé (option B).
HANDICAP_ENTIER_REMBOURSE = False

# V7 — écart max P_modèle / P_marché sur le 1X2 au-delà duquel on avertit.
SEUIL_COHERENCE_1X2 = 0.15

# V8 — fraîcheur des cotes (champ optionnel cotes_prises_le ; absent = silencieux).
FRAICHEUR_MAX_HEURES = 24

# V11 — statuts de match non analysables (comparés en minuscules).
STATUTS_INACTIFS = {"reporte", "reporté", "annule", "annulé", "reported", "cancelled", "canceled", "postponed"}

# V3 — plausibilité cote par famille de marché (détecte les cotes cassées, pas la vraisemblance sportive).
FOURCHETTES_V3: Dict[str, Tuple[float, float]] = {
    "1X2":         (1.01,  30.0),
    "BTTS":        (1.05,  15.0),
    "OU":          (1.01, 100.0),
    "BUTS_EQUIPE": (1.01,  50.0),
    "CLEAN_SHEET": (1.05,  30.0),
    "DC":          (1.02,  15.0),
    "HANDICAP":    (1.01, 100.0),
}

# ══════════════════════════════════════════════════════════════════════════
# INVENTAIRE DES MARCHÉS
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
# VALIDATION
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
    """V4 — lit matchs_joues. Invalide (0, négatif, non entier, non numérique, booléen) → absent, avec avertissement."""
    v = eq.get("matchs_joues")
    if v is None:
        return None, None
    if _entier_positif(v) and v >= 1:
        return int(v), None
    return None, f"matchs_joues invalide pour {eq.get('nom')} : {v!r} (ignoré)"


def verifier_v5_moyennes(nom: Any, attaque: float, defense: float) -> None:
    """V5 — moyennes de buts dans [0, MOYENNE_BUTS_MAX]. Lève ValueError « V5 : ... » sinon."""
    for v, champ in ((attaque, "buts_marques_moy"), (defense, "buts_encaisses_moy")):
        if v < 0:
            raise ValueError(f"V5 : {champ} = {v} < 0 pour {nom}")
        if v > MOYENNE_BUTS_MAX:
            raise ValueError(f"V5 : {champ} = {v} > {MOYENNE_BUTS_MAX} pour {nom}")


def preparer_equipe(eq: Any) -> Tuple[float, float, Optional[int], List[str]]:
    """3.2 / 2.1 — Retourne (attaque, défense, n_matchs, avertissements). Lève ValueError si invalide.

    Priorité pour n_matchs : matchs_recents (n = leur nombre) > matchs_joues (entier >= 1) > None.
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
# VÉRIFICATEURS V1-V11
# ══════════════════════════════════════════════════════════════════════════
def verifier_v1_marge_groupe(reconnus: Dict[str, float], groupes_complets: Set[str],
                             mid: Any) -> Tuple[Set[str], Dict[str, str]]:
    """V1 — Somme marge ∈ [1.00, 1.20] pour chaque groupe complet. Retourne (groupes_valides, rejets)."""
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
    """V2 — Cohérence dom/ext sur chaque demi-ligne de handicap (lignes entières hors périmètre)."""
    par_ligne: Dict[float, Dict[str, str]] = {}
    for cle, (side, H) in handicaps.items():
        par_ligne.setdefault(H, {})[side] = cle

    a_rejeter: Set[str] = set()
    exclusions: List[Dict[str, Any]] = []
    for H, cotes_par_side in par_ligne.items():
        if H == int(H):
            continue
        if "dom" not in cotes_par_side or "ext" not in cotes_par_side:
            continue
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
    """V3 — Plausibilité de chaque cote selon sa famille. Retourne (marches_a_rejeter, exclusions, avertissements)."""
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
    """V4 — Fiabilité des données du match (annotation, aucun rejet). Seule source : meta.fiabilite posé à la source.
    Le moteur n'infère JAMAIS FALLBACK depuis la forme des données."""
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
    """V8 — fraîcheur des cotes. Avertissement uniquement. Champ absent = silencieux. Sans fuseau = UTC."""
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
# λ ET MATRICE DE POISSON
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
# PROBABILITÉS PAR MARCHÉ
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
    """6.7 — (P_win_dom, P_push, P_win_ext) pour la ligne H appliquée au domicile."""
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
# EDGE, EV, DÉCISION DE VALUE
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
# STATUTS
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
# ARTEFACTS
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
# CATÉGORIES (ordre D → A → B → C)
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
# DÉSIGNATIONS ET VERDICT
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
# COHÉRENCE MARCHÉ
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
# ALGORITHME PAR MATCH
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
