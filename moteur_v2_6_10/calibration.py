# -*- coding: utf-8 -*-
"""Calibration isotone des probabilités du modèle (régression monotone, algorithme PAV).

Le moteur v2.6.9 n'a aucune calibration : ses probabilités sont trop extrêmes aux deux bouts (annoncé 11 % / réel 16 % ;
annoncé 89 % / réel 84 %). La calibration apprend, sur des matchs DÉJÀ JOUÉS, la correspondance « probabilité annoncée →
fréquence réellement observée ». Elle est monotone : une probabilité plus haute n'est jamais calibrée plus bas.

Règles (mêmes garde-fous que le moteur V3) :
  - il faut au moins MIN_OBSERVATIONS observations ET MIN_MATCHS matchs distincts : les ~25 marchés d'un même match
    sont tous liés au même score, 300 observations ne valent que 12 à 15 matchs ;
  - les marchés mathématiquement équivalents d'un même match ne comptent qu'une fois (ex. handicap -0,5 du domicile =
    victoire du domicile) ;
  - l'appelant ne doit fournir que des matchs joués AVANT le match à calibrer (voir `avant`) ;
  - sortie bornée à [PLANCHER ; PLAFOND] : une probabilité exactement 0 ou 1 n'est jamais une certitude.

Ce module ne lit aucun fichier et ne connaît ni équipe ni championnat : il reçoit des observations
{"match_id", "marche", "proba", "gagne"} (+ "date" facultative) et rend un objet sérialisable en JSON.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

MIN_OBSERVATIONS = 300
MIN_MATCHS = 50
PLANCHER = 0.01
PLAFOND = 0.99

_RE_HANDICAP = re.compile(r"^handicap_(dom|ext)_([+-]?)(\d+)_(\d)$")


def marche_equivalent(marche: str) -> str:
    """Représentant d'une classe de marchés mathématiquement équivalents (clés du moteur)."""
    if marche == "clean_sheet_dom":
        return "buts_ext_under_0_5"
    if marche == "clean_sheet_ext":
        return "buts_dom_under_0_5"
    m = _RE_HANDICAP.match(marche or "")
    if m:
        cote, signe, entier, dixieme = m.groups()
        ligne = int(entier) + int(dixieme) / 10.0
        if signe == "-":
            ligne = -ligne
        h = ligne if cote == "dom" else -ligne          # ligne appliquée au domicile (même convention que le moteur)
        if h == -0.5:
            return "victoire" if cote == "dom" else "dc_X2"
        if h == 0.5:
            return "dc_1X" if cote == "dom" else "defaite"
    return marche


def observation_valide(o: Any) -> bool:
    if not isinstance(o, dict) or o.get("match_id") is None or not isinstance(o.get("marche"), str):
        return False
    p, y = o.get("proba"), o.get("gagne")
    if isinstance(p, bool) or not isinstance(p, (int, float)) or not 0 < float(p) < 1:
        return False
    return y in (0, 1, True, False)


def avant(observations: Iterable[Dict[str, Any]], date_limite: str) -> List[Dict[str, Any]]:
    """Observations strictement antérieures à `date_limite` (AAAA-MM-JJ). Sans champ `date` : refusées (jamais de fuite)."""
    return [o for o in observations if isinstance(o.get("date"), str) and o["date"] < date_limite]


def dedoublonne(observations: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Une seule observation par (match, marché équivalent) ; les observations invalides sont écartées."""
    vues, out = set(), []
    for o in observations:
        if not observation_valide(o):
            continue
        cle = (o["match_id"], marche_equivalent(o["marche"]))
        if cle in vues:
            continue
        vues.add(cle)
        out.append(o)
    return out


def _pav(paires: Sequence[Tuple[float, int]]) -> Tuple[Tuple[float, float], ...]:
    """Régression isotone : blocs [somme p, somme y, n]. Retourne des points (p moyen du bloc, fréquence du bloc)."""
    blocs = [[p, float(y), 1] for p, y in sorted(paires)]
    i = 0
    while i < len(blocs) - 1:
        if blocs[i][1] / blocs[i][2] > blocs[i + 1][1] / blocs[i + 1][2]:
            blocs[i] = [blocs[i][0] + blocs[i + 1][0], blocs[i][1] + blocs[i + 1][1], blocs[i][2] + blocs[i + 1][2]]
            del blocs[i + 1]
            i = max(0, i - 1)
        else:
            i += 1
    return tuple((sp / n, sy / n) for sp, sy, n in blocs)


@dataclass(frozen=True)
class CalibrateurIsotone:
    points: Tuple[Tuple[float, float], ...]
    n_observations: int = 0
    n_matchs: int = 0

    @property
    def pret(self) -> bool:
        return len(self.points) > 0

    def predire(self, p: float) -> float:
        """Probabilité calibrée (interpolation linéaire entre les blocs), bornée à [PLANCHER ; PLAFOND]."""
        if not self.pret:
            raise ValueError("calibrateur non entraîné")
        p = min(max(float(p), 0.0), 1.0)
        pts = self.points
        if p <= pts[0][0]:
            y = pts[0][1]
        elif p >= pts[-1][0]:
            y = pts[-1][1]
        else:
            y = pts[-1][1]
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                if x1 <= p <= x2:
                    y = (y1 + y2) / 2.0 if x2 == x1 else y1 + (p - x1) / (x2 - x1) * (y2 - y1)
                    break
        return min(max(y, PLANCHER), PLAFOND)

    def to_dict(self) -> Dict[str, Any]:
        return {"schema": 1, "points": [list(p) for p in self.points],
                "n_observations": self.n_observations, "n_matchs": self.n_matchs}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CalibrateurIsotone":
        if not isinstance(d, dict) or d.get("schema") != 1:
            raise ValueError("calibrateur : schéma inconnu")
        pts = tuple((float(x), float(y)) for x, y in d.get("points", []))
        if any(b[1] < a[1] for a, b in zip(pts, pts[1:])):
            raise ValueError("calibrateur : points non monotones")
        return cls(pts, int(d.get("n_observations", 0)), int(d.get("n_matchs", 0)))


def apprendre(observations: Iterable[Dict[str, Any]], *, min_observations: int = MIN_OBSERVATIONS,
              min_matchs: int = MIN_MATCHS) -> Tuple[Optional[CalibrateurIsotone], Dict[str, Any]]:
    """(calibrateur ou None, diagnostic). None tant que l'échantillon est insuffisant : le moteur reste alors
    non calibré et le dit (jamais de calibration sur trop peu de matchs)."""
    obs = dedoublonne(observations)
    n_matchs = len({o["match_id"] for o in obs})
    diag: Dict[str, Any] = {"pret": False, "raison": "OK", "observations": len(obs), "matchs": n_matchs,
                            "minimum_observations": min_observations, "minimum_matchs": min_matchs}
    if len(obs) < min_observations:
        diag["raison"] = "OBSERVATIONS_INSUFFISANTES"
        return None, diag
    if n_matchs < min_matchs:
        diag["raison"] = "MATCHS_INSUFFISANTS"
        return None, diag
    points = _pav([(float(o["proba"]), 1 if o["gagne"] else 0) for o in obs])
    diag["pret"] = True
    diag["blocs"] = len(points)
    return CalibrateurIsotone(points, len(obs), n_matchs), diag
