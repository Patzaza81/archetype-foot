"""Module 2, branchement des paramètres du Module 1 dans Dixon-Coles (ordre de Patrick du 30/10/2026).

Quatre effets, chacun avec UNE force apprise hors échantillon (calibrage.py) ; une force nulle = effet sans action. Aucune valeur posée à la main.
1. Forme_PPM (34) → décroissance temporelle xi. Dynamique d'une équipe = |Forme_PPM − PPM| (la forme récente s'écarte de sa saison).
   Poids d'un match passé : exp(−xi × âge × exp(c_forme × dynamique moyenne des deux équipes du match)). Avec c_forme > 0, les équipes en
   pleine dynamique comptent surtout leurs derniers matchs (xi plus fort), comme demandé.
2. IE (38) → buts attendus : λ_dom × exp(c_ie × (IE_dom − 1)), λ_ext × exp(c_ie × (IE_ext − 1)) (IE au lieu du match, contrat 1.5).
   Avec c_ie > 0 une équipe qui gâche (IE < 0,8) voit son λ baisser ; l'apprentissage peut aussi trouver l'effet inverse ou nul.
3. Amplitude (31) et Score modal (32) → ρ : ρ = ρ_commun + c_amplitude × (amplitude moyenne des deux équipes au lieu − amplitude du championnat)
   + c_modal × (part des deux équipes dont le score modal au lieu est 0-0 ou 1-1 − même part dans le championnat). Borné à l'intervalle numérique de ρ.
4. Profil (41) croisé → λ : excédent de buts (réels − attendus par l'ajustement) de A à domicile contre des adversaires du profil de B, et de B à
   l'extérieur contre des adversaires du profil de A (marqués et encaissés). λ_dom × exp(c_style × (excédent marqué A + excédent encaissé B)),
   λ_ext × exp(c_style × (excédent marqué B + excédent encaissé A)). Pas de match contre ce profil : excédent 0 (aucun effet, rien deviné).
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from . import module1 as M1, modele as MO

NOMS = ("forme", "ie", "amplitude", "modal", "style")
NEUTRES = {k: 0.0 for k in NOMS}


def dynamique(t: dict[str, Any]) -> dict[str, float]:
    return {e: abs(p["forme_ppm"] - p["PPM"]) for e, p in t["equipes"].items() if p.get("forme_ppm") is not None}


def mult_xi(dom: list[str], ext: list[str], dyn: dict[str, float], c_forme: float) -> np.ndarray | None:
    """Multiplicateur de xi pour chaque match passé (None si l'effet est nul)."""
    if not c_forme:
        return None
    return np.exp(c_forme * np.array([(dyn.get(a, 0.0) + dyn.get(b, 0.0)) / 2 for a, b in zip(dom, ext)]))


def _bas(s: str | None) -> float:
    return 1.0 if s in M1.SCORES_FAIBLES_NULS else 0.0


def references(t: dict[str, Any]) -> dict[str, float]:
    eq = list(t["equipes"].values())
    parts = [_bas(p.get("score_modal_dom")) for p in eq if p.get("score_modal_dom")] + [_bas(p.get("score_modal_ext")) for p in eq if p.get("score_modal_ext")]
    return {"amplitude": t["ligue"]["amplitude"] or 0.0, "modal": (sum(parts) / len(parts)) if parts else 0.0}


def excedents(matchs: list[dict], dom: str, ext: str, jour: str, t: dict[str, Any], fit: MO.Ajustement) -> dict[str, Any]:
    """Excédents moyens de buts (réels − attendus) contre le profil de l'adversaire du jour, au lieu du match."""
    eq = t["equipes"]
    prof_a, prof_b = eq[dom]["profil_id"], eq[ext]["profil_id"]
    ma = [m for m in matchs if m["date"] < jour and m.get("h") is not None and m["dom"] == dom and (eq.get(m["ext"]) or {}).get("profil_id") == prof_b]
    mb = [m for m in matchs if m["date"] < jour and m.get("h") is not None and m["ext"] == ext and (eq.get(m["dom"]) or {}).get("profil_id") == prof_a]

    def ex(liste: list[dict], cote: str) -> float:
        if not liste:
            return 0.0
        tot = 0.0
        for m in liste:
            lh, la = fit.lambdas(m["dom"], m["ext"])
            tot += (m["h"] - lh) if cote == "h" else (m["a"] - la)
        return tot / len(liste)

    return {"a_marque": ex(ma, "h"), "a_encaisse": ex(ma, "a"), "b_marque": ex(mb, "a"), "b_encaisse": ex(mb, "h"), "n_a": len(ma), "n_b": len(mb),
            "profil_dom": prof_a, "profil_ext": prof_b}


def facteurs(c: dict[str, Any], t: dict[str, Any], exc: dict[str, Any]) -> dict[str, float]:
    """Variables des effets 2 à 4 pour un match (à partir du contrat 1.5 et des excédents)."""
    ref = references(t)
    sd = c["equipe_domicile"]["stats_agregees_dom"]
    se = c["equipe_exterieur"]["stats_agregees_ext"]
    return {"ie_dom": sd["ie"] - 1.0, "ie_ext": se["ie"] - 1.0,
            "amplitude": (sd["variance"] + se["variance"]) / 2 - ref["amplitude"],
            "modal": (_bas(sd["score_modal"]) + _bas(se["score_modal"])) / 2 - ref["modal"],
            "style_dom": exc["a_marque"] + exc["b_encaisse"], "style_ext": exc["b_marque"] + exc["a_encaisse"]}


def appliquer(lh: float, la: float, rho: float, f: dict[str, float], k: dict[str, float]) -> tuple[float, float, float]:
    lh2 = lh * math.exp(k.get("ie", 0.0) * f["ie_dom"] + k.get("style", 0.0) * f["style_dom"])
    la2 = la * math.exp(k.get("ie", 0.0) * f["ie_ext"] + k.get("style", 0.0) * f["style_ext"])
    r = rho + k.get("amplitude", 0.0) * f["amplitude"] + k.get("modal", 0.0) * f["modal"]
    return lh2, la2, min(max(r, MO.RHO_BORNES[0]), MO.RHO_BORNES[1])


def appliquer_vect(lh: np.ndarray, la: np.ndarray, rho: np.ndarray, F: dict[str, np.ndarray], k: dict[str, float]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    lh2 = lh * np.exp(k.get("ie", 0.0) * F["ie_dom"] + k.get("style", 0.0) * F["style_dom"])
    la2 = la * np.exp(k.get("ie", 0.0) * F["ie_ext"] + k.get("style", 0.0) * F["style_ext"])
    r = np.clip(rho + k.get("amplitude", 0.0) * F["amplitude"] + k.get("modal", 0.0) * F["modal"], *MO.RHO_BORNES)
    return lh2, la2, r
