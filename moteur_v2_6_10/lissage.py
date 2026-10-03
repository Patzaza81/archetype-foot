# -*- coding: utf-8 -*-
"""Lissage des moyennes de buts vers une référence, SPÉCIFIQUE AU RÔLE (domicile / extérieur).

Pourquoi : le moteur v2.6.9 prend les moyennes brutes de buts de chaque équipe. Sur 3 ou 4 matchs, une équipe qui a
marqué 3 buts par match est traitée comme une équipe qui en marque 3 « pour de bon » : le modèle devient trop
confiant (évaluation du 21/09/2026 : 52,8 % de choix gagnés pour 65,1 % annoncés).

Règle : valeur lissée = (n × valeur observée + K × référence) / (n + K).

POURQUOI DEUX RÉFÉRENCES (défaut corrigé à l'audit du 01/10/2026) : le moteur utilise les matchs À DOMICILE de l'équipe qui
reçoit et les matchs À L'EXTÉRIEUR de la visiteuse. Un domicile marque en moyenne plus qu'un extérieur. Avec une référence
unique (1,35), deux équipes parfaitement moyennes voyaient leur avantage du domicile rogné (P(domicile) 44,1 % → 41,0 % à
n = 5) : un biais systématique, au détriment du domicile, d'autant plus fort que l'échantillon est petit.

    équipe qui reçoit :   buts marqués (à domicile)  → REF_BUTS_DOM   ;  buts encaissés (à domicile)   → REF_BUTS_EXT
    équipe visiteuse  :   buts marqués (à l'ext.)    → REF_BUTS_EXT   ;  buts encaissés (à l'ext.)     → REF_BUTS_DOM

PARAMÈTRES FIXÉS À L'AVANCE, jamais estimés sur les 501 matchs du banc : K = 4 ; REF_BUTS_DOM = 1,50 ; REF_BUTS_EXT = 1,20
(total 2,70 buts par match, le même niveau que la référence 1,35 + 1,35 du moteur V3). Ce sont des ordres de grandeur
généraux du football, PAS des mesures sur tes championnats : `evaluation/compare_moteurs_v2.py --sensibilite` mesure
l'effet d'un autre choix (en lecture seule : ne jamais choisir le meilleur sur ce tableau).

Le lissage est une PRÉ-ÉTAPE : il remplace les moyennes de chaque équipe, puis le moteur v2.6.9 fait tout le reste. Les bornes
V5 sont contrôlées sur les valeurs BRUTES : une donnée aberrante n'est jamais « rattrapée » par le lissage.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isfinite
from typing import Any, Dict, Optional, Tuple

K_LISSAGE = 4.0
REF_BUTS_DOM = 1.50
REF_BUTS_EXT = 1.20
N_PAR_DEFAUT = 5            # effectif supposé quand le nombre de matchs est inconnu (neutre, signalé par le moteur)
MOYENNE_BUTS_MAX = 10.0     # même borne que V5 du moteur de base


@dataclass(frozen=True)
class ParametresLissage:
    k: float = K_LISSAGE
    ref_dom: float = REF_BUTS_DOM
    ref_ext: float = REF_BUTS_EXT

    def __post_init__(self) -> None:
        if not (self.k >= 0 and 0 < self.ref_dom <= MOYENNE_BUTS_MAX and 0 < self.ref_ext <= MOYENNE_BUTS_MAX):
            raise ValueError("paramètres de lissage invalides")

    def signature(self) -> str:
        return f"lissage:k={self.k:g};dom={self.ref_dom:g};ext={self.ref_ext:g}"


PARAMETRES_PAR_DEFAUT = ParametresLissage()


def _nombre(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and isfinite(float(v))


def _entier_positif(v: Any) -> bool:
    return _nombre(v) and v >= 0 and int(v) == v


def lisse(valeur: float, n: float, reference: float, k: float = K_LISSAGE) -> float:
    """(n × valeur + k × référence) / (n + k)."""
    if n < 0 or k < 0:
        raise ValueError("n et k doivent être positifs")
    if n + k == 0:
        return float(reference)
    return (n * float(valeur) + k * float(reference)) / (n + k)


def niveau_echantillon(n: Optional[int]) -> str:
    """Même échelle que le moteur V3."""
    if n is None:
        return "INCONNU"
    if n <= 0:
        return "IMPOSSIBLE"
    if n < 3:
        return "TRES_FAIBLE"
    if n < 5:
        return "FAIBLE"
    if n < 8:
        return "UTILISABLE"
    if n < 10:
        return "SOLIDE"
    return "TRES_SOLIDE"


def _lire_equipe(eq: Any) -> Optional[Tuple[float, float, Optional[int], str]]:
    """(attaque, défense, n, source) bruts si l'équipe est exploitable ; None sinon.
    None = on ne touche à rien : le moteur de base décidera (et refusera) avec ses propres messages."""
    if not isinstance(eq, dict):
        return None
    recents = eq.get("matchs_recents")
    if recents:
        gf, ga = [], []
        for m in recents:
            if not (isinstance(m, (list, tuple)) and len(m) == 2 and _entier_positif(m[0]) and _entier_positif(m[1])):
                return None
            gf.append(float(m[0]))
            ga.append(float(m[1]))
        att, dfn, n, source = fsum(gf) / len(gf), fsum(ga) / len(ga), len(recents), "matchs_recents"
    else:
        a, d = eq.get("buts_marques_moy"), eq.get("buts_encaisses_moy")
        if not (_nombre(a) and _nombre(d)):
            return None
        v = eq.get("matchs_joues")
        n = int(v) if (_nombre(v) and v >= 1 and int(v) == v) else None
        att, dfn, source = float(a), float(d), "moyennes"
    if not (0 <= att <= MOYENNE_BUTS_MAX and 0 <= dfn <= MOYENNE_BUTS_MAX):
        return None          # V5 : valeur aberrante, laissée telle quelle pour que le moteur la refuse
    return att, dfn, n, source


def lisser_equipe(eq: Any, role: str, params: ParametresLissage = PARAMETRES_PAR_DEFAUT) -> Tuple[Any, Optional[Dict[str, Any]]]:
    """(équipe lissée, trace). `role` = "dom" (équipe qui reçoit) ou "ext" (visiteuse). L'équipe d'origine n'est jamais
    modifiée. trace = None si rien n'a été lissé."""
    if role not in ("dom", "ext"):
        raise ValueError("role doit être 'dom' ou 'ext'")
    lu = _lire_equipe(eq)
    if lu is None:
        return eq, None
    att, dfn, n, source = lu
    ref_att, ref_def = (params.ref_dom, params.ref_ext) if role == "dom" else (params.ref_ext, params.ref_dom)
    n_utilise = n if n is not None else N_PAR_DEFAUT
    att_l, def_l = lisse(att, n_utilise, ref_att, params.k), lisse(dfn, n_utilise, ref_def, params.k)
    copie = {k: v for k, v in eq.items() if k != "matchs_recents"}
    copie["buts_marques_moy"] = att_l
    copie["buts_encaisses_moy"] = def_l
    if source == "matchs_recents":
        copie["matchs_joues"] = n
    trace = {
        "role": role, "n": n, "n_utilise": n_utilise, "niveau": niveau_echantillon(n),
        "poids_reference": params.k / (n_utilise + params.k) if (n_utilise + params.k) else 1.0,
        "reference_attaque": ref_att, "reference_defense": ref_def,
        "attaque_brute": att, "attaque_lissee": att_l,
        "defense_brute": dfn, "defense_lissee": def_l,
    }
    return copie, trace


def lisser_match(match: Any, params: ParametresLissage = PARAMETRES_PAR_DEFAUT) -> Tuple[Any, Dict[str, Any]]:
    """(match avec équipes lissées, trace). Le match d'origine n'est jamais modifié."""
    trace: Dict[str, Any] = {"signature": params.signature(), "k": params.k, "ref_dom": params.ref_dom,
                             "ref_ext": params.ref_ext, "dom": None, "ext": None}
    if not isinstance(match, dict):
        return match, trace
    dom, t_dom = lisser_equipe(match.get("equipe_dom"), "dom", params)
    ext, t_ext = lisser_equipe(match.get("equipe_ext"), "ext", params)
    out = dict(match)
    out["equipe_dom"], out["equipe_ext"] = dom, ext
    trace["dom"], trace["ext"] = t_dom, t_ext
    return out, trace
