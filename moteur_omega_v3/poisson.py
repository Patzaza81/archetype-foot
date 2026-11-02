"""Modèles de probabilité de buts (Poisson) pour Omega V3 : branche expérimentale du 02/11/2026, rien n'est branché en production. `python -m moteur_omega_v3.poisson`

Un modèle donne deux espérances de buts (domicile, extérieur) ; la loi des scores est le produit de deux lois de Poisson ; la probabilité d'un marché est la somme des
probabilités des scores qui le font gagner (même règlement que `marches.py`). Les probabilités sont ensuite CALIBRÉES sur l'historique (réussite réelle observée par
tranche de 5 points, rendue croissante) : le pourcentage affiché est une réussite mesurée, jamais la sortie brute du modèle.

Modèles (chacun testé seul, aucun n'est empilé sur un autre sans test) :
  C        Poisson sur la moyenne attaque / défense des quatre séquences (toute la saison au même lieu, 5 matchs minimum) (variante C de `variantes.py`) ;
  FORCE    forces de TOUT le championnat (tous les matchs avant le jour, quel que soit le lieu) : attaque = buts marqués par match / moyenne du championnat,
           défense = buts encaissés par match / moyenne ; λ domicile = moyenne des buts à domicile × attaque A × défense B, λ extérieur = moyenne des buts à
           l'extérieur × attaque B × défense A. Les points et la différence de buts du classement sont des conséquences de ces mêmes buts : pas de double compte ;
  MIXTE    moyenne des deux probabilités (C et FORCE).
Aucun Edge, EV ou « value » : la cote n'est qu'une information d'accès.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from . import calibrage as K, donnees as D, marches as M, variantes as Vr
from .audit import wilson

ROOT = Path(__file__).resolve().parent.parent
SORTIE = ROOT / "docs" / "omega_v3_poisson.json"
MODELES = ("C", "FORCE", "MIXTE")


def forces_championnat(matchs: list[dict], dom: str, ext: str, jour: str, minimum: int = D.MIN_MATCHS, poids_recent: float = 1.0, n_recent: int = 3) -> dict[str, float]:
    """Espérances de buts (domicile, extérieur) à partir de tous les matchs du championnat STRICTEMENT avant `jour` (le match lui-même exclu).
    `poids_recent` : poids des `n_recent` derniers matchs de chaque équipe (1 = tous égaux) : la forme est une PONDÉRATION, jamais un filtre.
    Lève ValueError si une équipe a moins de `minimum` matchs au total ou si le championnat n'a aucun match."""
    if poids_recent <= 0:
        raise ValueError("poids de la forme invalide")
    pris = [m for m in matchs if m["date"] < jour and not D._est_le_match(m, dom, ext, jour) and isinstance(m["h"], int) and isinstance(m["a"], int)]
    if not pris:
        raise ValueError("championnat sans match antérieur")
    moy_dom = sum(m["h"] for m in pris) / len(pris)
    moy_ext = sum(m["a"] for m in pris) / len(pris)
    moy = (moy_dom + moy_ext) / 2
    def bilan(e: str) -> tuple[float, float, int, float]:
        """Buts marqués et encaissés par match de l'équipe, moyennes pondérées (les `n_recent` derniers matchs pèsent `poids_recent`) ; n = nombre de matchs."""
        jeu = sorted((m for m in pris if e in (m["dom"], m["ext"])), key=lambda m: (m["date"], m["dom"], m["ext"]))
        pour = contre = tot = 0.0
        for q, m in enumerate(jeu):
            w = poids_recent if q >= len(jeu) - n_recent else 1.0
            p_, c_ = (m["h"], m["a"]) if m["dom"] == e else (m["a"], m["h"])
            pour, contre, tot = pour + w * p_, contre + w * c_, tot + w
        return pour, contre, len(jeu), tot
    pa, ca, na, ta = bilan(dom)
    pb, cb, nb, tb = bilan(ext)
    if na < minimum or nb < minimum:
        raise ValueError(f"données insuffisantes : {na} et {nb} matchs au total (il en faut {minimum})")
    att_a, def_a, att_b, def_b = (pa / ta) / moy, (ca / ta) / moy, (pb / tb) / moy, (cb / tb) / moy
    return {"lam_dom": moy_dom * att_a * def_b, "lam_ext": moy_ext * att_b * def_a, "n_a": na, "n_b": nb, "moy_dom": moy_dom, "moy_ext": moy_ext}


def proba_lambdas(lam_dom: float, lam_ext: float) -> np.ndarray:
    """Probabilité (non calibrée) de chaque marché pour deux espérances de buts."""
    return Vr.frequences(np.outer(Vr.poisson(lam_dom), Vr.poisson(lam_ext)))


class Calibreur:
    """Réussite réelle lissée en fonction de la probabilité du modèle, apprise sur un échantillon (tous marchés confondus, remboursés exclus).
    Tranches de 5 points → réussite rendue croissante (PAV) → points d'appui (probabilité moyenne de la tranche, réussite lissée) reliés par interpolation linéaire :
    deux marchés de probabilités différentes reçoivent deux pourcentages différents (pas de marches d'escalier, donc pas d'égalités artificielles)."""
    PAS = 0.05

    def __init__(self, P: np.ndarray, S: np.ndarray, V: np.ndarray) -> None:
        n, k, somme = [], [], []
        for lo in np.arange(0, 1 - 1e-9, self.PAS):
            m = V & (P >= lo - 1e-12) & ((P < lo + self.PAS - 1e-12) if lo < 1 - self.PAS - 1e-9 else (P <= 1 + 1e-12))
            n.append(int(m.sum()))
            k.append(float(S[m].sum()))
            somme.append(float(P[m].sum()))
        pleins = [j for j, a in enumerate(n) if a]
        lis = K._pav([n[j] for j in pleins], [k[j] for j in pleins])
        self.effectifs = n
        self.x = [somme[j] / n[j] for j in pleins]                       # probabilité moyenne du modèle dans la tranche
        self.y = [float(v) for v in lis]                                 # réussite réelle lissée
        self._tables()

    def _tables(self) -> None:
        self.table = np.interp((np.arange(0, 1 / self.PAS) + 0.5) * self.PAS, self.x, self.y)      # valeur au centre de chaque tranche (compatibilité, lecture)

    @classmethod
    def depuis(cls, x: list[float], y: list[float], effectifs: list[int]) -> "Calibreur":
        c = cls.__new__(cls)
        c.x, c.y, c.effectifs = list(x), list(y), list(effectifs)
        c._tables()
        return c

    def __call__(self, P: np.ndarray) -> np.ndarray:
        return np.interp(np.asarray(P, dtype=float), self.x, self.y)


def probabilites(ech: list[dict[str, Any]], ligues: D.Ligues) -> dict[str, np.ndarray]:
    """Probabilités brutes des trois modèles pour chaque match de l'échantillon (NaN si le modèle FORCE n'a pas assez de données)."""
    nm = len(M.CLES)
    out = {k: np.full((len(ech), nm), np.nan) for k in MODELES}
    for t, x in enumerate(ech):
        m = x["m"]
        s = D.sequences(ligues.matchs[m["ligue"]], m["eq_dom"], m["eq_ext"], m["jour"], n=D.TOUT_LE_LIEU)      # toute la saison au même lieu (≥ 5)
        out["C"][t] = Vr.frequences(Vr.poids("C", s["att_a"], s["def_a"], s["att_b"], s["def_b"]))
        m = x["m"]
        try:
            f = forces_championnat(ligues.matchs[m["ligue"]], m["eq_dom"], m["eq_ext"], m["jour"])
            out["FORCE"][t] = proba_lambdas(f["lam_dom"], f["lam_ext"])
            out["MIXTE"][t] = (out["C"][t] + out["FORCE"][t]) / 2
        except ValueError:
            pass
    return out


def proba_officielle(matchs: list[dict], dom: str, ext: str, jour: str, calibreurs: dict[str, "Calibreur"]) -> dict[str, Any]:
    """Pourcentage OFFICIEL d'un match : modèle MIXTE (C + FORCE) quand les quatre séquences (≥ 5 matchs au même lieu) existent, sinon FORCE seul (5 matchs au total par équipe suffisent),
    sinon rien. Chaque modèle est calibré par SON calibreur. Renvoie le modèle utilisé : jamais de mélange silencieux entre deux populations."""
    forces = None
    try:
        forces = forces_championnat(matchs, dom, ext, jour)
    except ValueError as e:
        raison_force = str(e)
    try:
        s = D.sequences(matchs, dom, ext, jour, n=D.TOUT_LE_LIEU)
    except ValueError as e:
        s, raison_seq = None, str(e)
    if forces is not None and s is not None:
        brut = (Vr.frequences(Vr.poids("C", s["att_a"], s["def_a"], s["att_b"], s["def_b"])) + proba_lambdas(forces["lam_dom"], forces["lam_ext"])) / 2
        return {"modele": "MIXTE", "brut": brut, "calibre": calibreurs["MIXTE"](brut)}
    if forces is not None:
        brut = proba_lambdas(forces["lam_dom"], forces["lam_ext"])
        return {"modele": "FORCE", "brut": brut, "calibre": calibreurs["FORCE"](brut)}
    return {"modele": None, "brut": None, "calibre": None, "raison": raison_force}


def mesure(P: np.ndarray, S: np.ndarray, V: np.ndarray, sel: np.ndarray) -> dict[str, Any]:
    p, y = P[sel & V], S[sel & V].astype(float)
    q = np.clip(p, 1e-3, 1 - 1e-3)
    return {"observations": int(len(p)), "annonce_moyenne": round(float(p.mean()), 4), "reel": round(float(y.mean()), 4), "ecart": round(float(p.mean() - y.mean()), 4),
            "brier": round(float(np.mean((p - y) ** 2)), 4), "log_loss": round(float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q))), 4)}


def top_par_match(Q: np.ndarray, F: np.ndarray, S: np.ndarray, V: np.ndarray, lignes: np.ndarray, k: int) -> dict[str, Any]:
    """Les k marchés les plus probables (calibrés) de chaque match, hors scores exacts et hors marchés vrais/faux dans tous les scénarios."""
    fam = np.array([M.famille(c) for c in M.CLES])
    ok = (fam != "scores exacts")[None, :] & (F > 0) & (F < 1) & V
    n = kk = 0
    ann = 0.0
    matchs = 0
    for t in np.where(lignes)[0]:
        q = np.where(ok[t] & ~np.isnan(Q[t]), Q[t], -1)
        if (q < 0).all():
            continue
        top = np.argsort(-q)[:k]
        matchs += 1
        n += len(top)
        kk += int(S[t, top].sum())
        ann += float(Q[t, top].sum())
    return {"matchs": matchs, "paris": n, "reussite": round(kk / n, 4) if n else None, "annonce_calibree": round(ann / n, 4) if n else None, "wilson_95": wilson(kk, n)}


def tout(log=print) -> dict[str, Any]:
    ligues = D.charger_ligues()
    ech, exclus = K.echantillon(log)
    ech = sorted(ech, key=lambda x: (x["m"]["jour"], x["m"]["id"]))
    jours = np.array([x["m"]["jour"] for x in ech])
    coupe = jours[int(len(ech) * K.PART_DEV)]
    dev, res = jours < coupe, jours >= coupe
    Y = np.array([x["y"] for x in ech])
    V, S = Y != 2, Y == 1
    F = np.array([x["f"] for x in ech])
    brut = probabilites(ech, ligues)
    fam = np.array([M.famille(c) for c in M.CLES])
    utile = (fam != "scores exacts")[None, :] & (F > 0) & (F < 1)        # marchés qui disent quelque chose (ni vrais ni faux partout)
    commun = ~np.isnan(brut["FORCE"][:, 0])                              # matchs où les trois modèles existent (comparaison à effectif égal)
    out: dict[str, Any] = {"echantillon": {"matchs": len(ech), "coupe": str(coupe), "developpement": int(dev.sum()), "reserve": int(res.sum()), "reserve_comparable": int((res & commun).sum()),
                                           "matchs_sans_forces": int((~commun).sum())}, "modeles": {}}
    for nom in MODELES:
        P = brut[nom]
        appr = dev & commun
        cal = Calibreur(P[appr], S[appr], V[appr])
        Q = np.where(np.isnan(P), np.nan, cal(np.nan_to_num(P)))
        sel = (res & commun)[:, None] & utile
        out["modeles"][nom] = {"brut": mesure(P, S, V, sel), "calibre": mesure(Q, S, V, sel),
                               "top_par_match": {str(k): top_par_match(Q, F, S, V, res & commun, k) for k in (1, 3, 5)},
                               "par_tranche_calibree": {f"{lo:.1f}-{lo + 0.1:.1f}": mesure(Q, S, V, sel & (Q >= lo - 1e-12) & (Q < lo + 0.1 - 1e-12 if lo < 0.9 else Q <= 1.0)) for lo in (0.0, 0.2, 0.4, 0.6, 0.8, 0.9)
                                                        if (sel & (Q >= lo - 1e-12) & (Q < lo + 0.1 - 1e-12 if lo < 0.9 else Q <= 1.0) & V).any()}}
    SORTIE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for nom, v in out["modeles"].items():
        log(f"{nom:6s} brut {v['brut']['brier']} / {v['brut']['log_loss']} | calibré {v['calibre']['brier']} / {v['calibre']['log_loss']} | écart {v['calibre']['ecart']:+} | top1 {v['top_par_match']['1']['reussite']} top3 {v['top_par_match']['3']['reussite']}")
    return out


if __name__ == "__main__":
    tout()
