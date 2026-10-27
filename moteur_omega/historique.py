"""Historique de réussite par type de pari (affiché sur la page à la place de la barre de « réussite attendue »).

Pourquoi : parmi les paris retenus, le pourcentage annoncé (62 à 70 %) ne distingue pas les paris entre eux (corrélation avec la réussite : 0,004 ;
tranches 67,5 / 65,2 / 69,8 / 69,0 %, aucun ordre). Ce qui les distingue, de façon stable sur les deux moitiés de la période, c'est le TYPE de pari
(buts du match : ~72 % des deux côtés ; résultat : ~61–62 %). On affiche donc la réussite réellement constatée du type de pari, avec le nombre de paris.

Méthode : mêmes règles que la production (analyse, sélection, pari principal) appliquées à tous les matchs joués de l'archive dont les cotes
ont été prises avant le coup d'envoi ; une réussite par famille de marché (`marches.famille`). Famille de moins de MIN_PARIS paris : non publiée.
Usage : python -m moteur_omega.historique  -> docs/omega_historique.json
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import coeur, donnees as D, marches as M

ROOT = Path(__file__).resolve().parent.parent
SORTIE = ROOT / "docs" / "omega_historique.json"
PARAMS = Path(__file__).with_name("parametres.json")
MIN_PARIS = 30          # en dessous, une réussite n'est pas publiée (trop imprécise)


def calculer(matchs: list[dict[str, Any]], refs: D.References, params: dict[str, Any]) -> dict[str, Any]:
    par: dict[str, list[bool]] = {}
    jours: list[str] = []
    for m in matchs:
        if m.get("h") is None:
            continue
        a = coeur.analyser(m, refs, params, avec_stabilite=False)
        if a["statut"] != "analyse":
            continue
        pr = coeur.selectionner(a, params["selection"])["principal"]
        if not pr:
            continue
        par.setdefault(pr["famille"], []).append(bool(M.test_du_marche(*pr["cle"])(m["h"], m["a"])))
        jours.append(m["jour"])
    familles = {f: {"n": len(v), "gagnes": sum(v), "reussite": round(sum(v) / len(v), 4)} for f, v in par.items() if len(v) >= MIN_PARIS}
    tous = [x for v in par.values() for x in v]
    return {"du": min(jours) if jours else None, "au": max(jours) if jours else None, "min_paris": MIN_PARIS, "familles": familles,
            "total": {"n": len(tous), "gagnes": sum(tous), "reussite": round(sum(tous) / len(tous), 4) if tous else None}}


def ecrire(sortie: Path = SORTIE, matchs: list[dict[str, Any]] | None = None, refs: D.References | None = None) -> dict[str, Any]:
    if matchs is None:
        matchs, refs = D.charger_archive(avec_futurs=False)
    out = calculer(matchs, refs, json.loads(PARAMS.read_text(encoding="utf-8")))
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(json.dumps(ecrire(), ensure_ascii=False, indent=1))
