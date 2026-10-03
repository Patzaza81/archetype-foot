# -*- coding: utf-8 -*-
"""Calibration isotone des probabilités du modèle (régression monotone, algorithme PAV).

Le moteur v2.6.9 n'a aucune calibration : ses probabilités sont trop extrêmes aux deux bouts (annoncé 11 % / réel 16 % ;
annoncé 89 % / réel 84 %). La calibration apprend, sur des matchs DÉJÀ JOUÉS, la correspondance « probabilité annoncée →
fréquence réellement observée ». Elle est monotone : une probabilité plus haute n'est jamais calibrée plus bas.

GARDE-FOUS (renforcés à l'audit du 01/10/2026) :
  - MODÈLE : un calibrateur n'est valable que pour le modèle qui a produit les probabilités d'apprentissage (signature
    `modele`, incluant les paramètres de lissage). Un calibrateur appris sur les probabilités de la v2.6.9 non lissée serait
    appliqué à des probabilités déjà corrigées : double correction. Le moteur l'ignore et le dit.
  - DATES : chaque observation porte la date de son match ; le calibrateur retient la plus récente (`date_max`). Le moteur
    refuse un calibrateur dont `date_max` n'est pas antérieure au match analysé (fuite d'information du futur).
  - SÉLECTION : les observations doivent venir de l'INVENTAIRE COMPLET des marchés (≈ 20 à 25 par match). Apprendre sur les
    seules value bets (celles que le modèle juge meilleures que le marché) mesure la malchance du modèle sur ce qu'il a
    choisi, pas sa fiabilité : l'apprentissage est refusé s'il y a moins de MIN_MARCHES_PAR_MATCH marchés par match.
  - TAILLE : au moins MIN_OBSERVATIONS observations ET MIN_MATCHS matchs distincts (les marchés d'un même match partagent
    un même score : ils ne sont pas indépendants), et jamais de bloc de moins de MIN_BLOC observations (sinon les queues de la
    courbe reposent sur quelques cas).
  - les marchés mathématiquement équivalents d'un même match ne comptent qu'une fois ;
  - POIDS : la correction apprise est elle-même bruitée (simulation de l'audit : sur 50 matchs, un modèle parfaitement calibré
    est déformé de 3,5 points en moyenne, 9 au pire). Elle est donc appliquée avec le poids n_matchs / (n_matchs + 100) :
    p_final = p + poids × (p_isotone − p). Mesuré en simulation, c'est meilleur que la correction pleine à toutes les tailles
    testées (50 à 500 matchs). Le poids reste monotone (somme de deux fonctions croissantes) ;
  - sortie bornée à [PLANCHER ; PLAFOND] : une probabilité exactement 0 ou 1 n'est jamais une certitude.

Ce module ne lit aucun fichier : il reçoit des observations {"match_id", "marche", "proba", "gagne", "date"} et rend un objet
sérialisable en JSON.
"""
from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

MIN_OBSERVATIONS = 300
MIN_MATCHS = 100                # V3 : 50. Doublé : ~20 marchés par match sont liés au même score (voir docs/AUDIT_MOTEUR_V2_6_10.md)
MIN_MARCHES_PAR_MATCH = 8       # un inventaire complet donne ~20 marchés ; des value bets seules, 1 à 3
MIN_BLOC = 30
K_CALIBRATION = 100              # poids du calibrateur = n_matchs / (n_matchs + K_CALIBRATION) : prudent tant que l'échantillon est petit
PLANCHER = 0.01
PLAFOND = 0.99
SCHEMA = 2

_RE_HANDICAP = re.compile(r"^handicap_(dom|ext)_([+-]?)(\d+)_(\d)$")
_RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


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
    if not (isinstance(o.get("date"), str) and _RE_DATE.match(o["date"])):
        return False                                       # sans date : impossible de vérifier l'antériorité
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


def _pav(paires: Sequence[Tuple[float, int]]) -> List[List[float]]:
    """Régression isotone : blocs [somme p, somme y, n], croissants en fréquence."""
    blocs = [[p, float(y), 1] for p, y in sorted(paires)]
    i = 0
    while i < len(blocs) - 1:
        if blocs[i][1] / blocs[i][2] > blocs[i + 1][1] / blocs[i + 1][2]:
            blocs[i] = [blocs[i][0] + blocs[i + 1][0], blocs[i][1] + blocs[i + 1][1], blocs[i][2] + blocs[i + 1][2]]
            del blocs[i + 1]
            i = max(0, i - 1)
        else:
            i += 1
    return blocs


def _fusionne_petits_blocs(blocs: List[List[float]], min_bloc: int) -> List[List[float]]:
    """Fusionne tout bloc de moins de `min_bloc` observations avec son voisin le plus proche en probabilité moyenne.
    Fusionner deux blocs voisins d'une régression isotone garde la monotonie (la moyenne pondérée reste entre les deux)."""
    blocs = [list(b) for b in blocs]
    while len(blocs) > 1:
        i = next((j for j, b in enumerate(blocs) if b[2] < min_bloc), None)
        if i is None:
            break
        if i == 0:
            k = 1
        elif i == len(blocs) - 1:
            k = i - 1
        else:
            gauche = abs(blocs[i][0] / blocs[i][2] - blocs[i - 1][0] / blocs[i - 1][2])
            droite = abs(blocs[i][0] / blocs[i][2] - blocs[i + 1][0] / blocs[i + 1][2])
            k = i - 1 if gauche <= droite else i + 1
        a, b = min(i, k), max(i, k)
        blocs[a] = [blocs[a][0] + blocs[b][0], blocs[a][1] + blocs[b][1], blocs[a][2] + blocs[b][2]]
        del blocs[b]
    return blocs


@dataclass(frozen=True)
class CalibrateurIsotone:
    points: Tuple[Tuple[float, float], ...]
    n_observations: int = 0
    n_matchs: int = 0
    modele: str = ""                       # signature du modèle dont il calibre les probabilités
    date_max: Optional[str] = None         # date du match le plus récent utilisé pour l'apprentissage

    @property
    def pret(self) -> bool:
        return len(self.points) > 0

    @property
    def poids(self) -> float:
        """Part de la correction isotone effectivement appliquée (0 → aucune, 1 → pleine)."""
        return self.n_matchs / (self.n_matchs + K_CALIBRATION) if self.n_matchs > 0 else 1.0

    def predire(self, p: float) -> float:
        """Probabilité calibrée : p + poids × (courbe isotone interpolée − p), bornée à [PLANCHER ; PLAFOND]."""
        if not self.pret:
            raise ValueError("calibrateur non entraîné")
        p = min(max(float(p), 0.0), 1.0)
        pts = self.points
        if p <= pts[0][0]:
            y = pts[0][1]
        elif p >= pts[-1][0]:
            y = pts[-1][1]
        else:
            i = bisect_right([x for x, _ in pts], p) - 1          # pts[i].x <= p < pts[i+1].x
            (x1, y1), (x2, y2) = pts[i], pts[i + 1]
            y = (y1 + y2) / 2.0 if x2 == x1 else y1 + (p - x1) / (x2 - x1) * (y2 - y1)
        y = p + self.poids * (y - p)
        return min(max(y, PLANCHER), PLAFOND)

    def to_dict(self) -> Dict[str, Any]:
        return {"schema": SCHEMA, "points": [list(p) for p in self.points], "n_observations": self.n_observations,
                "n_matchs": self.n_matchs, "modele": self.modele, "date_max": self.date_max}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CalibrateurIsotone":
        if not isinstance(d, dict) or d.get("schema") != SCHEMA:
            raise ValueError("calibrateur : schéma inconnu")
        pts = tuple((float(x), float(y)) for x, y in d.get("points", []))
        if any(b[1] < a[1] or b[0] < a[0] for a, b in zip(pts, pts[1:])):
            raise ValueError("calibrateur : points non monotones")
        return cls(pts, int(d.get("n_observations", 0)), int(d.get("n_matchs", 0)), str(d.get("modele", "")), d.get("date_max"))


def apprendre(observations: Iterable[Dict[str, Any]], *, modele: str, min_observations: int = MIN_OBSERVATIONS,
              min_matchs: int = MIN_MATCHS, min_marches_par_match: int = MIN_MARCHES_PAR_MATCH,
              min_bloc: int = MIN_BLOC) -> Tuple[Optional[CalibrateurIsotone], Dict[str, Any]]:
    """(calibrateur ou None, diagnostic). None tant que l'échantillon est insuffisant ou biaisé : le moteur reste alors
    non calibré et le dit. `modele` (obligatoire) = signature du modèle qui a produit les probabilités (voir
    moteur_v2_6_10.core.signature_modele)."""
    if not isinstance(modele, str) or not modele:
        raise ValueError("`modele` obligatoire : signature du modèle dont on calibre les probabilités")
    brutes = list(observations)
    obs = dedoublonne(brutes)
    n_matchs = len({o["match_id"] for o in obs})
    diag: Dict[str, Any] = {"pret": False, "raison": "OK", "observations": len(obs), "ecartees": len(brutes) - len(obs),
                            "matchs": n_matchs, "marches_par_match": (len(obs) / n_matchs) if n_matchs else 0.0,
                            "minimum_observations": min_observations, "minimum_matchs": min_matchs}
    if len(obs) < min_observations:
        diag["raison"] = "OBSERVATIONS_INSUFFISANTES"
        return None, diag
    if n_matchs < min_matchs:
        diag["raison"] = "MATCHS_INSUFFISANTS"
        return None, diag
    if diag["marches_par_match"] < min_marches_par_match:
        diag["raison"] = "ECHANTILLON_BIAISE_PAR_SELECTION"
        return None, diag
    blocs = _fusionne_petits_blocs(_pav([(float(o["proba"]), 1 if o["gagne"] else 0) for o in obs]), min_bloc)
    points = tuple((sp / n, sy / n) for sp, sy, n in blocs)
    diag["pret"] = True
    diag["blocs"] = len(points)
    return CalibrateurIsotone(points, len(obs), n_matchs, modele, max(o["date"][:10] for o in obs)), diag
