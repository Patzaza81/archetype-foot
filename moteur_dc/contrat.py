"""Module 1.5 du moteur DC (Section A du Module 2 de Patrick) : contrat de données `match_input` d'un match, et ses contrôles stricts.

Toute erreur lève ValueError : le match est alors EXCLU de l'analyse, la raison est gelée au journal (jamais corrigée en silence).
Contrôles : 1. Filtre 0 (≥ 4 matchs à domicile pour l'équipe domicile, ≥ 4 à l'extérieur pour l'équipe extérieur) ; 2. types numériques ;
3. aucune valeur manquante ou NaN ; 4. historiques d'au moins 4 matchs, dates AAAA-MM-JJ en ordre chronologique (deux matchs le même jour
pour la même équipe = donnée douteuse, rejetée).
"""
from __future__ import annotations

import math
import re
from typing import Any

from . import donnees as D, module1 as M1

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CHAMPS_AGREGES = ("moy_bp", "moy_bc", "taux_nul", "variance", "ie", "forme_ppm", "ppm")


def _bloc(p: dict[str, Any], lieu: str) -> dict[str, Any]:
    return {"moy_bp": p.get(f"MBM_{lieu}"), "moy_bc": p.get(f"MBE_{lieu}"), "taux_nul": p.get(f"TN_{lieu}"),
            "score_modal": p.get(f"score_modal_{lieu}"), "variance": p.get(f"amplitude_{lieu}"), "ie": p.get(f"IE_{lieu}"),
            "forme_ppm": p.get(f"forme_ppm_{lieu}"), "ppm": p.get(f"PPM_{lieu}")}


def construire(matchs: list[dict], dom: str, ext: str, jour: str, t: dict[str, Any] | None = None, match_id: str | None = None) -> dict[str, Any]:
    """match_input.json du match (dom reçoit ext le `jour`). `t` = tableau du Module 1 au même jour (recalculé s'il manque). ValueError si invalide."""
    t = t or M1.tableau(matchs, jour)
    pd, pe = t["equipes"].get(dom), t["equipes"].get(ext)
    nd = pd["J_dom"] if pd else 0
    ne = pe["J_ext"] if pe else 0
    if nd < D.MIN_MATCHS or ne < D.MIN_MATCHS:
        raise ValueError(f"Filtre 0 : {nd} match(s) à domicile pour {dom}, {ne} à l'extérieur pour {ext} (il en faut {D.MIN_MATCHS})")
    c = {"match_id": match_id or f"{dom}_vs_{ext}", "jour": jour,
         "league_context": {"moyenne_buts_ligue": t["ligue"]["moyenne_buts"], "amplitude_ligue": t["ligue"]["amplitude"], "matchs": t["ligue"]["matchs"]},
         "equipe_domicile": {"nom": dom, "style_tag": pd["style_tag"], "profil_id": pd["profil_id"], "matchs_joues_dom": nd,
                             "stats_agregees_dom": _bloc(pd, "dom"), "historique_matchs_dom": M1.historique_lieu(matchs, dom, True, jour, t)},
         "equipe_exterieur": {"nom": ext, "style_tag": pe["style_tag"], "profil_id": pe["profil_id"], "matchs_joues_ext": ne,
                              "stats_agregees_ext": _bloc(pe, "ext"), "historique_matchs_ext": M1.historique_lieu(matchs, ext, False, jour, t)},
         "constantes_championnat": {"CBD": t["ligue"]["CBD"], "CBE": t["ligue"]["CBE"]}, "gap": M1.gap(t, dom, ext)}
    valider(c)
    return c


def _nombre(x: Any, nom: str) -> None:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError(f"{nom} : valeur non numérique ({x!r})")
    if math.isnan(x) or math.isinf(x):
        raise ValueError(f"{nom} : NaN ou infini")


def valider(c: dict[str, Any]) -> None:
    for cote, lieu, n_cle in (("equipe_domicile", "dom", "matchs_joues_dom"), ("equipe_exterieur", "ext", "matchs_joues_ext")):
        e = c[cote]
        _nombre(e[n_cle], f"{cote}.{n_cle}")
        if e[n_cle] < D.MIN_MATCHS:
            raise ValueError(f"Filtre 0 : {e['nom']} n'a que {e[n_cle]} match(s) au lieu")
        _nombre(e["profil_id"], f"{cote}.profil_id")
        if e["profil_id"] not in M1.PROFILS:
            raise ValueError(f"{cote}.profil_id hors 1 à 5")
        if not isinstance(e["style_tag"], str) or not e["style_tag"]:
            raise ValueError(f"{cote}.style_tag manquant")
        s = e[f"stats_agregees_{lieu}"]
        for k in CHAMPS_AGREGES:
            _nombre(s.get(k), f"{cote}.{k}")
        if not isinstance(s.get("score_modal"), str):
            raise ValueError(f"{cote}.score_modal manquant")
        h = e[f"historique_matchs_{lieu}"]
        if len(h) < D.MIN_MATCHS:
            raise ValueError(f"{cote} : historique de {len(h)} match(s), il en faut {D.MIN_MATCHS}")
        for x in h:
            if not isinstance(x.get("date"), str) or not _DATE.match(x["date"]):
                raise ValueError(f"{cote} : date invalide {x.get('date')!r}")
            _nombre(x.get("buts_pour"), f"{cote}.buts_pour")
            _nombre(x.get("buts_contre"), f"{cote}.buts_contre")
        dates = [x["date"] for x in h]
        if any(a >= b for a, b in zip(dates, dates[1:])):
            raise ValueError(f"{cote} : historique pas en ordre chronologique strict")
    for k in ("CBD", "CBE"):
        _nombre(c["constantes_championnat"].get(k), k)
    _nombre(c["league_context"].get("moyenne_buts_ligue"), "moyenne_buts_ligue")
