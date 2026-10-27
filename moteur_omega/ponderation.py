"""Marché pondéré (affichage, ordre de Patrick du 27/10/2026) : le marché le plus probable parmi ceux dont la cote est SUPÉRIEURE à 1,22,
affiché à côté du pari principal pour voir d'un coup d'œil s'ils vont dans le même sens.

Probabilité pondérée = régression logistique de la réussite réelle sur : la probabilité du modèle, la probabilité de la cote (marge retirée) et
la fréquence du pari dans les derniers matchs affichés (moyenne et minimum des deux équipes). Les poids sont APPRIS sur l'archive (jamais fixés à la main) et
écrits dans docs/omega_ponderation.json à chaque passage du pipeline. Mesuré le 27/10/2026 (développement avant le 14/10, test après) : le poids de la cote
domine, celui du modèle est nul ou négatif, celui des derniers matchs est faible ; réussite ≈ 75 % pour une cote moyenne ≈ 1,27, rendement ≈ −5 %.
C'est donc une information (« le marché le plus probable »), pas un pari rentable.

Ne touche ni à la sélection du moteur, ni au journal, ni aux pronostics gelés.
Usage : python -m moteur_omega.ponderation  -> docs/omega_ponderation.json
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from . import coeur, donnees as D, marches as M

ROOT = Path(__file__).resolve().parent.parent
SORTIE = ROOT / "docs" / "omega_ponderation.json"
PARAMS = Path(__file__).with_name("parametres.json")
COTE_MIN = 1.22          # ordre de Patrick : cote strictement supérieure
MIN_MATCHS_LIEU = 4      # comme le moteur : au moins 4 matchs au même lieu pour chaque équipe


def _logit(p: float) -> float:
    p = min(max(float(p), 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def _vecteur(p: float, p_cote: float, f_dom: float, f_ext: float) -> list[float]:
    return [1.0, _logit(p), _logit(p_cote), (f_dom + f_ext) / 2 - 0.5, min(f_dom, f_ext) - 0.5]


def candidats(m: dict[str, Any], a: dict[str, Any]) -> list[dict[str, Any]]:
    """Marchés du match à cote > COTE_MIN, avec leur test, leurs fréquences dans les derniers matchs (≥ 4 par équipe) et leur vecteur."""
    if a.get("statut") != "analyse":
        return []
    dm = D.derniers_matchs(m)
    out = []
    for l in a["marches"]:
        c = l.get("cote")
        if not c or c <= COTE_MIN or l.get("p_cote") is None:
            continue
        t = M.test_du_marche(*l["cle"])
        if t is None:
            continue
        r = D.pari_sur_derniers(t, dm)
        if not r or r["dom"]["n"] < MIN_MATCHS_LIEU or r["ext"]["n"] < MIN_MATCHS_LIEU:
            continue
        fd, fx = r["dom"]["ok"] / r["dom"]["n"], r["ext"]["ok"] / r["ext"]["n"]
        out.append({"ligne": l, "test": t, "x": _vecteur(l["p"], l["p_cote"], fd, fx)})
    return out


def _ajuster_logistique(X: np.ndarray, y: np.ndarray, iterations: int = 50) -> np.ndarray:
    w = np.zeros(X.shape[1])
    for _ in range(iterations):
        p = 1 / (1 + np.exp(-X @ w))
        poids = p * (1 - p) + 1e-9
        w = w + np.linalg.solve((X * poids[:, None]).T @ X + 1e-6 * np.eye(X.shape[1]), X.T @ (y - p))
    return w


def ajuster(matchs: list[dict[str, Any]], refs: D.References, params: dict[str, Any]) -> dict[str, Any]:
    """Apprend les poids sur les matchs joués de l'archive (cotes prises avant le coup d'envoi)."""
    X, y = [], []
    for m in matchs:
        if m.get("h") is None:
            continue
        a = coeur.analyser(m, refs, params, avec_stabilite=False)
        for c in candidats(m, a):
            X.append(c["x"])
            y.append(float(bool(c["test"](m["h"], m["a"]))))
    if len(y) < 500:
        raise ValueError(f"trop peu de marchés pour apprendre les poids ({len(y)})")
    X, y = np.array(X), np.array(y)
    w = _ajuster_logistique(X, y)
    p = 1 / (1 + np.exp(-X @ w))
    return {"cote_min": COTE_MIN, "n_marches": int(len(y)),
            "poids": dict(zip(["constante", "logit_modele", "logit_cote", "frequence_moyenne", "frequence_minimale"], [round(float(v), 4) for v in w])),
            "brier": round(float(np.mean((p - y) ** 2)), 4), "brier_cote_seule": round(float(np.mean((1 / (1 + np.exp(-X[:, 2])) - y) ** 2)), 4)}


def probabilite(poids: dict[str, float], x: list[float]) -> float:
    w = [poids[k] for k in ("constante", "logit_modele", "logit_cote", "frequence_moyenne", "frequence_minimale")]
    return 1 / (1 + math.exp(-sum(a * b for a, b in zip(w, x))))


def choisir(m: dict[str, Any], a: dict[str, Any], ajustement: dict[str, Any] | None) -> dict[str, Any] | None:
    """Le marché de plus forte probabilité pondérée (cote > 1,22) ; None sans poids appris ou sans candidat. Aucun seuil inventé."""
    if not ajustement:
        return None
    meilleur = None
    for c in candidats(m, a):
        p = probabilite(ajustement["poids"], c["x"])
        if meilleur is None or (p, c["ligne"]["cote"]) > (meilleur[0], meilleur[1]["cote"]):
            meilleur = (p, c["ligne"])
    if meilleur is None:
        return None
    p, l = meilleur
    return {"cle": l["cle"], "marche": l["marche"], "valeur_reelle": l.get("valeur_reelle"), "famille": l["famille"], "cote": l["cote"], "p": round(p, 4)}


def harmonie(cle_principal: list[str] | None, cle_pondere: list[str] | None) -> str | None:
    """Comparaison des deux paris sur les scores qui les font gagner : « identique » (même événement), « meme_sens » (l'un contient l'autre :
    si le plus étroit gagne, l'autre gagne aussi) ou « different » (chacun peut gagner sans l'autre)."""
    if not cle_principal or not cle_pondere:
        return None
    a, b = M.signature(tuple(cle_principal)), M.signature(tuple(cle_pondere))
    if a == b:
        return "identique"
    return "meme_sens" if a < b or b < a else "different"


def charger(chemin: Path = SORTIE) -> dict[str, Any] | None:
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except Exception:
        return None


def ecrire(sortie: Path = SORTIE, matchs: list[dict[str, Any]] | None = None, refs: D.References | None = None) -> dict[str, Any]:
    if matchs is None:
        matchs, refs = D.charger_archive(avec_futurs=False)
    out = ajuster(matchs, refs, json.loads(PARAMS.read_text(encoding="utf-8")))
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(json.dumps(ecrire(), ensure_ascii=False, indent=1))
