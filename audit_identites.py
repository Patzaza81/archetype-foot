"""Audit des identités du chargeur de Gamma (01/11/2026) : tout rattachement d'un alias doit pouvoir être prouvé par un identifiant
indépendant du nom et du score. Source de la preuve : `url_match` (lien du match chez Matchendirect), qui porte un identifiant unique du
match ; le même match vu des deux côtés a le même identifiant. Aucun seuil, aucune ressemblance de nom ou de score.

    python audit_identites.py [data/assemblage/equipes.json]

Lecture seule : ne modifie ni l'assemblage ni le chargeur."""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from moteur_dc import donnees as D

ID_MATCH = re.compile(r"_([a-z0-9]{20,})\.html")


def id_match(url: Any) -> str | None:
    m = ID_MATCH.search(str(url or ""))
    return m.group(1) if m else None


def _noms(doc: dict[str, Any]) -> dict[str, dict[str, str]]:
    noms: dict[str, dict[str, str]] = defaultdict(dict)
    for x in doc["equipes"]:
        for n in (x.get("nom_football_data"), x.get("nom_matchendirect")):
            if n:
                noms[x["competition"]][D.norm(n)] = x["cle_cache"]
        s = D._slug(x["cle_cache"])
        if s:
            noms[x["competition"]].setdefault(s, x["cle_cache"])
    return noms


def preuves_par_identifiant(doc: dict[str, Any]) -> dict[tuple[str, str], dict[str, set[str]]]:
    """(championnat, alias normalisé) -> {club du cache: identifiants de match prouvant que l'alias est ce club}.
    Un alias cité par l'équipe t sur le match i est le club u si le bloc de u contient aussi le match i."""
    noms = _noms(doc)
    par_id: dict[tuple[str, str], set[str]] = defaultdict(set)
    cites: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for x in doc["equipes"]:
        for m in x.get("matchs") or []:
            i = id_match(m.get("url_match"))
            if i and m.get("adversaire"):
                par_id[(x["competition"], i)].add(x["cle_cache"])
                cites[(x["competition"], i)].append((x["cle_cache"], D.norm(m["adversaire"])))
    preuves: dict[tuple[str, str], dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for (lg, i), recs in cites.items():
        for t, al in recs:
            if noms[lg].get(al) is not None:
                continue
            for u in par_id[(lg, i)] - {t}:
                preuves[(lg, al)][u].add(i)
    return preuves


def alias_rattaches(doc: dict[str, Any], ligues: D.Ligues | None = None) -> list[dict[str, Any]]:
    """Alias inconnus que le chargeur a rattachés à un club du cache, avec le nombre de citations."""
    ligues = ligues or D.Ligues(doc)
    noms = _noms(doc)
    cles = {x["cle_cache"] for x in doc["equipes"]}
    cit: dict[tuple[str, str], int] = defaultdict(int)
    for x in doc["equipes"]:
        propres = {D.norm(n) for n in (x.get("nom_football_data"), x.get("nom_matchendirect")) if n}
        for m in x.get("matchs") or []:
            al = D.norm(m.get("adversaire") or "")
            if al and al not in noms[x["competition"]] and al not in propres and m.get("date"):
                cit[(x["competition"], al)] += 1
    out = []
    for (lg, al), n in cit.items():
        club = ligues._uf.trouve(f"?{lg}|{al}")
        if club in cles:
            out.append({"championnat": lg, "alias": al, "club": club, "citations": n})
    return out


def auditer(doc: dict[str, Any], ligues: D.Ligues | None = None) -> dict[str, Any]:
    preuves = preuves_par_identifiant(doc)
    rows = alias_rattaches(doc, ligues)
    sans, contredits = [], []
    for r in rows:
        p = preuves.get((r["championnat"], r["alias"])) or {}
        if r["club"] not in p:
            (contredits if p else sans).append(r)
    return {"alias_rattaches": len(rows), "prouves_par_identifiant": len(rows) - len(sans) - len(contredits),
            "sans_preuve_d_identifiant": sans, "contredits_par_identifiant": contredits}


if __name__ == "__main__":
    chemin = Path(sys.argv[1]) if len(sys.argv) > 1 else D.ASSEMBLAGE
    r = auditer(json.loads(chemin.read_text(encoding="utf-8")))
    print(json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in r.items()}, ensure_ascii=False))
    for k in ("sans_preuve_d_identifiant", "contredits_par_identifiant"):
        for x in r[k][:20]:
            print(k, x)
