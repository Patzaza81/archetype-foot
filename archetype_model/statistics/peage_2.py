"""
archetype_model/statistics/peage_2.py
=====================================
Pipeline complet du Péage 2 — Version 2.3 (Compatibilité P1 verrouillée)

Chaîne :
    1. Validation des profils P1 en entrée.
    2. Calcul des lambdas à partir des volumes bruts du Péage 1.
    3. Génération de la matrice de Poisson bivariée.
    4. Agrégation vers les 27 marchés cibles.
    5. Construction de la fréquence de référence P1 croisée (1X2 aligné).
    6. Filtrage P1 vs P2 : écart borné + seuil par marché.

Contrat d'entrée :
    - profil_dom, profil_ext : sorties COMPLÈTES de profil_equipe.py.
      Chacune doit contenir "profil_global.volumes_bruts" et
      "profil_global.n_valides".
    - freq_p1_dom, freq_p1_ext : fréquences BRUTES, déjà filtrées sur
      les marchés validés P1. Utiliser `extraire_frequences_p1_validees()`
      pour les préparer proprement.

Invariants :
    - Zéro cote, zéro bookmaker.
    - Aucune exception silencieuse : toutes les anomalies sont exposées.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple, Any, Final, Optional


# =============================================================
# CONSTANTES PARTAGÉES AVEC P1
# =============================================================

MARCHES_CIBLES: Final[Tuple[str, ...]] = (
    "victoire", "nul", "defaite",
    "over_0_5", "over_1_5", "over_2_5", "over_3_5",
    "under_0_5", "under_1_5", "under_2_5", "under_3_5",
    "btts_oui", "btts_non",
    "buts_marques_over_0_5", "buts_marques_over_1_5", "buts_marques_over_2_5",
    "buts_marques_under_0_5", "buts_marques_under_1_5", "buts_marques_under_2_5",
    "buts_encaisses_over_0_5", "buts_encaisses_over_1_5", "buts_encaisses_over_2_5",
    "buts_encaisses_under_0_5", "buts_encaisses_under_1_5", "buts_encaisses_under_2_5",
    "clean_sheet", "encaisse_au_moins_1",
)

MIN_LAMBDA: Final[float] = 0.05
MAX_LAMBDA: Final[float] = 10.0
MAX_BUTS: Final[int] = 10

SEUIL_ECART_MAX: Final[float] = 0.18
FACTEUR_ECART_SEUIL: Final[float] = 0.50

SEUILS_PAR_MARCHE: Final[Dict[str, float]] = {
    "victoire": 0.46, "nul": 0.26, "defaite": 0.28,
    "over_0_5": 0.55, "under_0_5": 0.07,
    "over_1_5": 0.55, "under_1_5": 0.26,
    "over_2_5": 0.55, "under_2_5": 0.44,
    "over_3_5": 0.28, "under_3_5": 0.55,
    "btts_oui": 0.55, "btts_non": 0.55,
    "buts_marques_over_0_5": 0.55, "buts_marques_under_0_5": 0.19,
    "buts_marques_over_1_5": 0.43, "buts_marques_under_1_5": 0.55,
    "buts_marques_over_2_5": 0.15, "buts_marques_under_2_5": 0.55,
    "buts_encaisses_over_0_5": 0.55, "buts_encaisses_under_0_5": 0.28,
    "buts_encaisses_over_1_5": 0.40, "buts_encaisses_under_1_5": 0.55,
    "buts_encaisses_over_2_5": 0.12, "buts_encaisses_under_2_5": 0.55,
    "clean_sheet": 0.27, "encaisse_au_moins_1": 0.55,
}

_MAPPING_ENCAISSES_VERS_MARQUES: Final[Dict[str, str]] = {
    "buts_encaisses_over_0_5": "buts_marques_over_0_5",
    "buts_encaisses_over_1_5": "buts_marques_over_1_5",
    "buts_encaisses_over_2_5": "buts_marques_over_2_5",
    "buts_encaisses_under_0_5": "buts_marques_under_0_5",
    "buts_encaisses_under_1_5": "buts_marques_under_1_5",
    "buts_encaisses_under_2_5": "buts_marques_under_2_5",
}


# =============================================================
# 0. PONT P1 -> P2
# =============================================================

def valider_profil_p1(profil: Dict[str, Any]) -> List[str]:
    anomalies: List[str] = []

    if not isinstance(profil, dict):
        return ["profil_non_dict"]

    pg = profil.get("profil_global")
    if not isinstance(pg, dict):
        anomalies.append("profil_global_absent")
        return anomalies

    if not isinstance(pg.get("volumes_bruts"), dict):
        anomalies.append("volumes_bruts_absent")
    else:
        vb = pg["volumes_bruts"]
        for cle in ("moy_gf", "moy_ga"):
            valeur = vb.get(cle)
            if not isinstance(valeur, (int, float)) or isinstance(valeur, bool):
                anomalies.append(f"volumes_bruts.{cle}_invalide")

    n_valides = pg.get("n_valides")
    if not isinstance(n_valides, int) or isinstance(n_valides, bool):
        anomalies.append("n_valides_invalide")

    return anomalies


def extraire_frequences_p1_validees(profil_p1: Dict[str, Any]) -> Dict[str, float]:
    pr = profil_p1.get("profil_role", {})
    freq_brutes = pr.get("frequences_brutes", {})
    marches_valides = pr.get("marches_valides_p1", {})

    return {
        marche: freq_brutes[marche]
        for marche, valide in marches_valides.items()
        if valide and marche in freq_brutes
    }


# =============================================================
# 1. CALCUL DES LAMBDAS
# =============================================================

def borner_lambda(valeur: float) -> float:
    return max(MIN_LAMBDA, min(MAX_LAMBDA, valeur))


def calculer_lambdas_match(
    profil_dom: Dict[str, Any],
    profil_ext: Dict[str, Any],
) -> Dict[str, Any]:
    anomalies_dom = valider_profil_p1(profil_dom)
    anomalies_ext = valider_profil_p1(profil_ext)

    vol_dom = profil_dom.get("profil_global", {}).get("volumes_bruts", {})
    vol_ext = profil_ext.get("profil_global", {}).get("volumes_bruts", {})

    att_dom = vol_dom.get("moy_gf", 0.0) or 0.0
    def_dom = vol_dom.get("moy_ga", 0.0) or 0.0
    att_ext = vol_ext.get("moy_gf", 0.0) or 0.0
    def_ext = vol_ext.get("moy_ga", 0.0) or 0.0

    lambda_dom = borner_lambda((att_dom + def_ext) / 2.0)
    lambda_ext = borner_lambda((att_ext + def_dom) / 2.0)

    return {
        "lambda_dom": round(lambda_dom, 4),
        "lambda_ext": round(lambda_ext, 4),
        "n_global_dom": profil_dom.get("profil_global", {}).get("n_valides", 0),
        "n_global_ext": profil_ext.get("profil_global", {}).get("n_valides", 0),
        "anomalies_profil_dom": anomalies_dom,
        "anomalies_profil_ext": anomalies_ext,
    }


# =============================================================
# 2. MATRICE DE POISSON
# =============================================================

def calculer_poisson_unitaire(k: int, lambda_val: float) -> float:
    if lambda_val <= 0:
        return 1.0 if k == 0 else 0.0
    return (math.pow(lambda_val, k) * math.exp(-lambda_val)) / math.factorial(k)


def generer_matrice_poisson(
    lambda_dom: float,
    lambda_ext: float,
    max_buts: int = MAX_BUTS,
) -> List[List[float]]:
    prob_dom = [calculer_poisson_unitaire(i, lambda_dom) for i in range(max_buts + 1)]
    prob_ext = [calculer_poisson_unitaire(j, lambda_ext) for j in range(max_buts + 1)]

    return [
        [round(prob_dom[i] * prob_ext[j], 6) for j in range(max_buts + 1)]
        for i in range(max_buts + 1)
    ]


# =============================================================
# 3. PROBABILITÉS DE MARCHÉS
# =============================================================

def calculer_probabilites_marches(matrice: List[List[float]]) -> Dict[str, float]:
    max_d = len(matrice)
    max_e = len(matrice[0]) if max_d > 0 else 0

    probs: Dict[str, float] = {m: 0.0 for m in MARCHES_CIBLES}

    for i in range(max_d):
        for j in range(max_e):
            p = matrice[i][j]
            total = i + j

            if i > j:
                probs["victoire"] += p
            elif i == j:
                probs["nul"] += p
            else:
                probs["defaite"] += p

            if total > 0.5: probs["over_0_5"] += p
            else: probs["under_0_5"] += p
            if total > 1.5: probs["over_1_5"] += p
            else: probs["under_1_5"] += p
            if total > 2.5: probs["over_2_5"] += p
            else: probs["under_2_5"] += p
            if total > 3.5: probs["over_3_5"] += p
            else: probs["under_3_5"] += p

            if i > 0 and j > 0: probs["btts_oui"] += p
            else: probs["btts_non"] += p

            if i > 0.5: probs["buts_marques_over_0_5"] += p
            else: probs["buts_marques_under_0_5"] += p
            if i > 1.5: probs["buts_marques_over_1_5"] += p
            else: probs["buts_marques_under_1_5"] += p
            if i > 2.5: probs["buts_marques_over_2_5"] += p
            else: probs["buts_marques_under_2_5"] += p

            if j > 0.5: probs["buts_encaisses_over_0_5"] += p
            else: probs["buts_encaisses_under_0_5"] += p
            if j > 1.5: probs["buts_encaisses_over_1_5"] += p
            else: probs["buts_encaisses_under_1_5"] += p
            if j > 2.5: probs["buts_encaisses_over_2_5"] += p
            else: probs["buts_encaisses_under_2_5"] += p

            if j == 0: probs["clean_sheet"] += p
            else: probs["encaisse_au_moins_1"] += p

    return {m: round(v, 4) for m, v in probs.items()}


# =============================================================
# 4. FRÉQUENCE DE RÉFÉRENCE P1
# =============================================================

def _moyenne_si_dispo(v1: Optional[float], v2: Optional[float]) -> Optional[float]:
    if v1 is None and v2 is None: return None
    if v1 is None: return v2
    if v2 is None: return v1
    return (v1 + v2) / 2.0


def construire_frequence_reference(
    freq_dom: Dict[str, float],
    freq_ext: Dict[str, float],
) -> Tuple[Dict[str, float], List[str]]:
    ref: Dict[str, float] = {}
    absents: List[str] = []

    v = _moyenne_si_dispo(freq_dom.get("victoire"), freq_ext.get("defaite"))
    if v is not None: ref["victoire"] = v
    else: absents.append("victoire")

    v = _moyenne_si_dispo(freq_dom.get("defaite"), freq_ext.get("victoire"))
    if v is not None: ref["defaite"] = v
    else: absents.append("defaite")

    v = _moyenne_si_dispo(freq_dom.get("nul"), freq_ext.get("nul"))
    if v is not None: ref["nul"] = v
    else: absents.append("nul")

    for m in (
        "over_0_5", "over_1_5", "over_2_5", "over_3_5",
        "under_0_5", "under_1_5", "under_2_5", "under_3_5",
        "btts_oui", "btts_non",
    ):
        v = _moyenne_si_dispo(freq_dom.get(m), freq_ext.get(m))
        if v is not None: ref[m] = v
        else: absents.append(m)

    for m in (
        "buts_marques_over_0_5", "buts_marques_over_1_5", "buts_marques_over_2_5",
        "buts_marques_under_0_5", "buts_marques_under_1_5", "buts_marques_under_2_5",
    ):
        if m in freq_dom: ref[m] = freq_dom[m]
        else: absents.append(m)

    for m_enc, m_marq in _MAPPING_ENCAISSES_VERS_MARQUES.items():
        v = _moyenne_si_dispo(freq_dom.get(m_enc), freq_ext.get(m_marq))
        if v is not None: ref[m_enc] = v
        else: absents.append(m_enc)

    v = _moyenne_si_dispo(freq_dom.get("clean_sheet"), freq_ext.get("buts_marques_under_0_5"))
    if v is not None: ref["clean_sheet"] = v
    else: absents.append("clean_sheet")

    v = _moyenne_si_dispo(
        freq_dom.get("encaisse_au_moins_1"),
        freq_ext.get("buts_marques_over_0_5"),
    )
    if v is not None: ref["encaisse_au_moins_1"] = v
    else: absents.append("encaisse_au_moins_1")

    return ref, absents


# =============================================================
# 5. FILTRAGE P1 vs P2
# =============================================================

def _ecart_max_effectif(seuil_marche: float) -> float:
    return max(SEUIL_ECART_MAX, FACTEUR_ECART_SEUIL * seuil_marche)


def filtrer_et_croiser_marches(
    freq_reference: Dict[str, float],
    probabilites_p2: Dict[str, float],
    seuils_marche: Dict[str, float] = SEUILS_PAR_MARCHE,
) -> Dict[str, Any]:
    valides: Dict[str, Any] = {}
    rejetes: Dict[str, Any] = {}

    for marche, freq_p1 in freq_reference.items():
        prob_p2 = probabilites_p2.get(marche, 0.0)
        seuil = seuils_marche.get(marche, 0.55)
        ecart = abs(freq_p1 - prob_p2)
        ecart_max = _ecart_max_effectif(seuil)

        statut = {
            "freq_p1": round(freq_p1, 4),
            "prob_p2": round(prob_p2, 4),
            "ecart": round(ecart, 4),
            "ecart_max": round(ecart_max, 4),
            "seuil_marche": seuil,
        }

        if ecart <= ecart_max and prob_p2 >= seuil:
            statut["valide"] = True
            valides[marche] = statut
        else:
            statut["valide"] = False
            motifs = []
            if ecart > ecart_max:
                motifs.append("ecart_p1_p2_trop_eleve")
            if prob_p2 < seuil:
                motifs.append("probabilite_p2_insuffisante")
            statut["motifs"] = motifs
            rejetes[marche] = statut

    return {
        "nb_marches_analyses": len(freq_reference),
        "nb_valides": len(valides),
        "marches_valides": valides,
        "marches_rejetes": rejetes,
    }


# =============================================================
# 6. CHEF D'ORCHESTRE
# =============================================================

def executer_peage_2(
    profil_dom: Dict[str, Any],
    profil_ext: Dict[str, Any],
    freq_p1_dom: Optional[Dict[str, float]] = None,
    freq_p1_ext: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    if freq_p1_dom is None:
        freq_p1_dom = extraire_frequences_p1_validees(profil_dom)
    if freq_p1_ext is None:
        freq_p1_ext = extraire_frequences_p1_validees(profil_ext)

    lambdas = calculer_lambdas_match(profil_dom, profil_ext)
    matrice = generer_matrice_poisson(lambdas["lambda_dom"], lambdas["lambda_ext"])
    probs_p2 = calculer_probabilites_marches(matrice)
    freq_ref, marches_absents = construire_frequence_reference(freq_p1_dom, freq_p1_ext)
    filtrage = filtrer_et_croiser_marches(freq_ref, probs_p2)

    return {
        "lambdas": lambdas,
        "probabilites_p2": probs_p2,
        "frequences_reference": freq_ref,
        "filtrage": filtrage,
        "meta": {
            "version": "2.3",
            "n_marches_reference": len(freq_ref),
            "n_marches_absents": len(marches_absents),
            "marches_absents": marches_absents,
        },
    }


# =============================================================
# EXEMPLE D'EXÉCUTION
# =============================================================

if __name__ == "__main__":
    from pprint import pprint

    profil_dom = {
        "equipe": "Équipe A", "role": "domicile",
        "profil_role": {
            "n_valides": 5, "c_n": 0.75,
            "frequences_brutes": {
                "victoire": 0.60, "nul": 0.20, "defaite": 0.20,
                "over_2_5": 0.60, "btts_oui": 0.60,
                "buts_marques_over_0_5": 0.80,
                "clean_sheet": 0.30, "encaisse_au_moins_1": 0.70,
            },
            "frequences_effectives": {},
            "marches_valides_p1": {
                "victoire": True, "nul": False, "defaite": False,
                "over_2_5": True, "btts_oui": True,
                "buts_marques_over_0_5": True,
                "clean_sheet": False, "encaisse_au_moins_1": True,
            },
        },
        "disponibilite": {"a_des_donnees": True, "a_un_marche_valide": True},
        "profil_global": {
            "n_valides": 12,
            "volumes_bruts": {
                "total_gf": 24, "total_ga": 15,
                "moy_gf": 2.0, "moy_ga": 1.25,
            },
        },
    }
    profil_ext = {
        "equipe": "Équipe B", "role": "exterieur",
        "profil_role": {
            "n_valides": 5, "c_n": 0.75,
            "frequences_brutes": {
                "victoire": 0.30, "nul": 0.30, "defaite": 0.40,
                "over_2_5": 0.50, "btts_oui": 0.55,
                "buts_marques_over_0_5": 0.65,
            },
            "frequences_effectives": {},
            "marches_valides_p1": {
                "victoire": False, "nul": False, "defaite": True,
                "over_2_5": True, "btts_oui": True,
                "buts_marques_over_0_5": True,
            },
        },
        "disponibilite": {"a_des_donnees": True, "a_un_marche_valide": True},
        "profil_global": {
            "n_valides": 10,
            "volumes_bruts": {
                "total_gf": 12, "total_ga": 18,
                "moy_gf": 1.2, "moy_ga": 1.8,
            },
        },
    }

    resultat = executer_peage_2(profil_dom, profil_ext)
    pprint(resultat)