"""Palier 2 des tickets alpha (25/10/2026, demande de Patrick : « des marchés prometteurs au deuxième palier »).

Un seul marché, retenu parce qu'il a tenu sur les cotes BetPawa réelles de l'archive ARCHETYPE (étude du 25/10/2026, 802 matchs) :
« l'équipe à domicile ne marque pas plus de 2 buts » (total de buts du domicile, moins de 2,5). Quand la probabilité estimée par les
chiffres dépassait d'au moins 10 % la probabilité de la cote (probabilité × cote − 1 > 0,10) : 53 paris, 77 % gagnés, +20 % ; sur la
période la plus récente : 46 paris, +17 %. « Les deux équipes ne marquent pas », d'abord positif (+24 %), est retombé à 0 % sur la période
récente : il n'est PAS retenu. Ces résultats viennent d'un seul mois : le palier 2 est suivi (gel avant le match, résultats, bilan) dans
`tickets.py` pour être confirmé ou abandonné sur des matchs qui n'ont pas servi à le trouver.

Probabilité estimée (lecture de l'étude, inchangée) : buts attendus du domicile λ = (moyenne de buts marqués à domicile de l'équipe qui
reçoit + moyenne de buts encaissés à l'extérieur de l'adversaire) / 2 sur leurs 10 derniers matchs au même lieu (au moins 5 chacun, comme le
palier 1), loi de Poisson : P(au plus 2 buts). Bibliothèque standard seulement (le pipeline n'a ni numpy ni scipy).
"""
from __future__ import annotations

import math
from typing import Any

DERNIERS = 10            # matchs au même lieu lus (étude du 25/10/2026)
MATCHS_MIN = 5           # au moins 5 de chaque côté (même exigence que le palier 1)
AVANTAGE_MIN = 0.10      # probabilité estimée × cote − 1 (étude du 25/10/2026)
COTE_MIN = 1.25          # comme partout dans l'alpha
CLE = ["over_under_domicile_2.5", "moins"]
MARCHE = "Moins de 2,5 buts du domicile"


def _lieu(equipe: dict | None, domicile: bool, jour: str) -> list[dict]:
    ms = [x for x in (equipe or {}).get("matchs") or [] if bool(x.get("domicile")) is bool(domicile) and not x.get("provisoire")
          and str(x.get("date"))[:10] < jour and isinstance(x.get("buts_marques"), int) and isinstance(x.get("buts_encaisses"), int)]
    ms.sort(key=lambda x: str(x["date"]))
    return ms[-DERNIERS:]


def p_au_plus(lam: float, k: int) -> float:
    return sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(k + 1))


def selections(equipe_dom: dict | None, equipe_ext: dict | None, jour: str, cotes_betpawa: dict | None) -> list[dict[str, Any]]:
    """Paris du palier 2 pour un match (0 ou 1). Rien sans cote BetPawa, sans 5 matchs de chaque côté, ou sans avantage suffisant."""
    hd, aw = _lieu(equipe_dom, True, jour), _lieu(equipe_ext, False, jour)
    if len(hd) < MATCHS_MIN or len(aw) < MATCHS_MIN:
        return []
    cote = ((cotes_betpawa or {}).get(CLE[0]) or {}).get(CLE[1])
    if not isinstance(cote, (int, float)) or cote < COTE_MIN:
        return []
    marques = sum(x["buts_marques"] for x in hd) / len(hd)
    encaisses = sum(x["buts_encaisses"] for x in aw) / len(aw)
    lam = (marques + encaisses) / 2
    p = p_au_plus(lam, 2)
    avantage = p * cote - 1
    if avantage <= AVANTAGE_MIN:
        return []
    return [{"cle": list(CLE), "marche": MARCHE, "cote": float(cote), "p_estimee": round(p, 4), "p_cote": round(1 / cote, 4),
             "avantage": round(avantage, 4), "buts_attendus": round(lam, 2), "n_domicile": len(hd), "n_exterieur": len(aw),
             "domicile_au_plus_2": [sum(1 for x in hd if x["buts_marques"] <= 2), len(hd)],
             "exterieur_encaisse_au_plus_2": [sum(1 for x in aw if x["buts_encaisses"] <= 2), len(aw)]}]
