"""Sélections calibrées de l'alpha (branchées le 24/10/2026, ordre de Patrick « Branche le nouveau moteur et adapte-le au système »).

Production des règles validées par la campagne d'optimisation (`campagne.py`, commit a15e5a4) :
- seules les règles de statut « exploitable » (confirmées sur la période réservée, contrôle des faux positifs) sont utilisées ;
- règles GELÉES lues dans `data/alpha_serie/campagne_regles.json` : rien n'est recalculé ni réappris ici ;
- lecture identique à la campagne (`robustesse.parts_marche`) sur les équipes figées avant le coup d'envoi ;
- cote minimale 1,25 : une cote connue en dessous rend le pari non proposable ; cote absente : « cote à lire » ;
- deux marchés qui sont le même événement (ex. victoire domicile = handicap −0,5 domicile) ne sont proposés qu'une fois.
Ce module ne dépend que de la bibliothèque standard (le pipeline n'a ni numpy ni scipy). Il ne modifie pas la méthode de l'alpha (`coeur.py`) :
il ajoute l'onglet « calibrees » à côté des trois onglets existants. Aucune rentabilité n'est démontrée (voir docs/ALPHA_SERIE.md).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import coeur, parametres as P
from . import robustesse as R

FICHIER = Path(__file__).resolve().parent.parent / "data" / "alpha_serie" / "campagne_regles.json"
_CATALOGUE: dict[str, tuple] | None = None


def _catalogue() -> dict[str, tuple]:
    """{libellé: (clé, condition, grilles du marché, grilles des jambes)} — calculé une seule fois."""
    global _CATALOGUE
    if _CATALOGUE is None:
        _CATALOGUE = {}
        for cle, lib, pred, zero in R.catalogue():
            gj = [R._solide_simple(jp, jz) for jp, jz in pred.jambes] if getattr(pred, "jambes", None) else None
            _CATALOGUE[lib] = (cle, pred, R.grilles(pred, zero), gj)
    return _CATALOGUE


def charger_regles(fichier: Path = FICHIER) -> list[dict[str, Any]]:
    """Règles exploitables seulement, dans l'ordre de la plus forte preuve (q-valeur finale croissante)."""
    try:
        d = json.loads(fichier.read_text(encoding="utf-8"))
    except Exception:
        return []
    regles = [r for r in (d.get("regles") or {}).values() if r.get("statut") == "exploitable" and r.get("marche") in _catalogue()]
    return sorted(regles, key=lambda r: (r.get("q_final") if r.get("q_final") is not None else 1.0, r["marche"]))


def cote_combo(cotes_betpawa: dict | None, cle: tuple | list) -> float | None:
    """Cote BetPawa d'un combiné calibré, lue dans les groupes du lecteur des combinés (parse_combines_betpawa.py) :
    (« combo », « 1N+moins_3.5 ») -> dc_total_3.5 / « 1N|moins » ; (« combo », « N2+btts_oui ») -> dc_btts / « N2|Oui ». Absente : None."""
    try:
        dc, jambe = str(cle[1]).split("+")
    except ValueError:
        return None
    if jambe.startswith(("plus_", "moins_")):
        sens, ligne = jambe.split("_")
        groupe, sel = f"dc_total_{ligne}", f"{dc}|{sens}"
    elif jambe in ("btts_oui", "btts_non"):
        groupe, sel = "dc_btts", f"{dc}|{'Oui' if jambe == 'btts_oui' else 'Non'}"
    else:
        return None
    v = ((cotes_betpawa or {}).get(groupe) or {}).get(sel)
    return float(v) if isinstance(v, (int, float)) and v > 1 else None


def categories(cote: float | None) -> list[str]:
    """Même règle que la campagne : sous 1,25 aucune catégorie ; sans cote : « toutes » ; sinon « toutes » + A ou B."""
    if cote is None:
        return ["toutes"]
    if cote < P.COTE_MIN:
        return []
    return ["toutes", "A" if cote < R.FRONTIERE_VOIES - 1e-12 else "B"]


def selections(equipe_dom: dict, equipe_ext: dict, jour: str, cotes_betpawa: dict | None, regles: list[dict] | None = None) -> list[dict[str, Any]]:
    """Sélections calibrées d'un match. Équipes figées (matchs strictement avant `jour`). Aucune issue n'est lue."""
    regles = charger_regles() if regles is None else regles
    if not regles:
        return []
    hm, hc = coeur.serie_lieu(equipe_dom, True, jour)
    am, ac = coeur.serie_lieu(equipe_ext, False, jour)
    prs = R.paires(hm, hc, am, ac)
    if len(prs) < P.MIN_MATCHS:
        return []
    cat = _catalogue()
    out, vus = [], set()
    for r in regles:
        cle, pred, gm, gj = cat[r["marche"]]
        if len(prs) < r["n_min"]:
            continue
        d, h = R.parts_marche(prs, cle, gm, gj)
        if d < r["marge_defavorable"] - 1e-9 or h < r["marge_habituelle"] - 1e-9:
            continue
        if cle[0] == "combo":                          # 24/10/2026 : cotes des combinés lues quand la collecte les fournit
            cote = cote_combo(cotes_betpawa, cle)
        else:
            cote = coeur.cote_de(cotes_betpawa, cle) if cle[0] not in R.ETUDIES_SANS_COTE else None
        if r["categorie"] not in categories(cote):
            continue
        evenement = tuple(bool(pred(a, b)) for a in range(11) for b in range(11))
        if evenement in vus:
            continue
        vus.add(evenement)
        tf = r.get("test_final") or {}
        out.append({"cle": list(cle), "marche": r["marche"], "famille": R.famille(cle), "cote": cote, "cote_a_lire": cote is None,
                    "valeur": tf.get("reussite"), "reussite_test_final": tf.get("reussite"), "reussite_sans_filtre": tf.get("reussite_sans_filtre"),
                    "paris_test_final": tf.get("paris"), "q_final": r.get("q_final"), "part_defavorable": round(d, 4), "part_habituelle": round(h, 4)})
    return out


def gagne(cle: list[str], h: int, a: int) -> bool | None:
    """Issue d'une sélection calibrée (tous les marchés du catalogue, combos compris)."""
    for c, pred, _, _ in _catalogue().values():
        if list(c) == list(cle):
            return bool(pred(h, a))
    return None
