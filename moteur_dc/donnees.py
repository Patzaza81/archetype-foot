"""Données du moteur DC : tous les matchs d'un championnat (pas seulement ceux des deux équipes).

Deux sources, comme omega mais lues ici de façon autonome :
- bloc Football-Data (`data/bloc_saisons/`) : calibrage et validation. Identités propres (noms Football-Data), saison ET division séparées ;
- assemblage des équipes (`data/assemblage/equipes.json`, lu par le contrat du système) : production. Chaque équipe y liste SES matchs
  (adversaire en texte). Le championnat entier se reconstruit en dédoublonnant les matchs vus des deux côtés ; l'identité d'un adversaire
  mal orthographié se démontre par les faits (même jour, même score, même équipe connue en face), jamais par un seuil de ressemblance.

Anti-fuite : un match n'entre dans l'ajustement d'une prédiction que s'il est strictement antérieur au jour du match. Aucune saison passée.
Règle de Patrick conservée : une prédiction exige au moins 4 matchs au même lieu pour chaque équipe.
"""
from __future__ import annotations

import glob
import gzip
import json
import re
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BLOC = ROOT / "data" / "bloc_saisons" / "bloc_2526_2627.json.gz"
ASSEMBLAGE = ROOT / "data" / "assemblage" / "equipes.json"
ARCHIVE = ROOT / "data" / "archive_test"
MIN_MATCHS = 4


def norm(s: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", str(s).lower()).encode("ascii", "ignore").decode())


def jours(d: str, ref: str) -> int:
    return (date.fromisoformat(ref[:10]) - date.fromisoformat(d[:10])).days


# --- Football-Data (calibrage) ------------------------------------------------------------------------------------
def charger_bloc(chemin: Path = BLOC) -> list[dict[str, Any]]:
    """Matchs du bloc, triés par date. `ligue` = saison + division : une équipe n'a jamais de matchs d'une autre saison."""
    out = []
    for m in json.load(gzip.open(chemin))["liste"]:
        out.append({"id": m["id"], "ligue": f"fd|{m['saison']}|{m['division']}", "saison": m["saison"], "date": m["date"][:10],
                    "dom": m["domicile"], "ext": m["exterieur"], "h": m["buts_dom"], "a": m["buts_ext"], "cotes": m.get("cotes") or {}})
    return sorted(out, key=lambda m: (m["date"], m["id"]))


# --- Assemblage (production) --------------------------------------------------------------------------------------
class _UF:
    def __init__(self) -> None:
        self.p: dict[str, str] = {}

    def trouve(self, x: str) -> str:
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def unir(self, a: str, b: str) -> None:
        ra, rb = self.trouve(a), self.trouve(b)
        if ra != rb:
            self.p[rb] = ra


def _slug(cle: str) -> str:
    m = re.search(r"/equipe/(.+)_[a-z0-9]{20,}\.html", cle)
    return norm(m.group(1)) if m else ""


class Ligues:
    """Championnats reconstitués depuis l'assemblage. `matchs[ligue]` = matchs uniques ; `equipe(cle)` = identité d'une équipe."""

    def __init__(self, doc: dict[str, Any]) -> None:
        eqs = doc["equipes"]
        noms: dict[str, dict[str, str]] = defaultdict(dict)          # ligue -> nom normalisé -> clé d'équipe
        for x in eqs:
            lg = x["competition"]
            for n in (x.get("nom_football_data"), x.get("nom_matchendirect")):
                if n:
                    noms[lg][norm(n)] = x["cle_cache"]
            if _slug(x["cle_cache"]):
                noms[lg].setdefault(_slug(x["cle_cache"]), x["cle_cache"])
        uf = _UF()
        vus: dict[tuple, list[tuple[str, bool]]] = defaultdict(list)    # (date, équipe, lieu, buts pour, buts contre) -> [(adversaire, résolu)]
        recs = []
        for x in eqs:
            lg, t = x["competition"], x["cle_cache"]
            for m in x.get("matchs") or []:
                if not m.get("date") or not m.get("adversaire") or not isinstance(m.get("buts_marques"), int) or not isinstance(m.get("buts_encaisses"), int):
                    continue
                o = noms[lg].get(norm(m["adversaire"]))
                resolu = o is not None
                o = o or f"?{lg}|{norm(m['adversaire'])}"
                recs.append((lg, m["date"][:10], t, bool(m["domicile"]), o, m["buts_marques"], m["buts_encaisses"], resolu))
                vus[(m["date"][:10], t, bool(m["domicile"]), m["buts_marques"], m["buts_encaisses"])].append((o, resolu))
        # un adversaire non reconnu est la même équipe que celle qui, dans son propre bloc, voit la nôtre à la même date avec le même score
        for lg, d, t, dom, o, gm, gc, resolu in recs:
            if not resolu:
                continue
            for o2, r2 in vus.get((d, o, not dom, gc, gm), []):
                if not r2:
                    uf.unir(t, o2)
        # alias restants (nom écrit par les autres équipes autrement que le nom propre de l'équipe) : l'alias désigne l'équipe qui, aux dates
        # où cet alias est cité, a elle-même un match au score inverse contre l'équipe qui le cite ; l'alias est rattaché à l'équipe qui
        # y gagne le plus de dates (égalité = rien n'est deviné)
        par_date: dict[tuple, list] = defaultdict(list)
        for r in recs:
            par_date[(r[0], r[1])].append(r)
        votes: dict[str, dict[str, int]] = defaultdict(dict)
        for lg, d, t, dom, o, gm, gc, resolu in recs:
            if resolu:
                continue
            for lg2, d2, u, dom2, o2, gm2, gc2, res2 in par_date[(lg, d)]:
                if u != t and dom2 != dom and gm2 == gc and gc2 == gm and (o2 == t or not res2):
                    votes[o][u] = votes[o].get(u, 0) + 1
        for alias, v in votes.items():
            top = sorted(v.items(), key=lambda kv: -kv[1])
            if len(top) == 1 or top[0][1] > top[1][1]:
                uf.unir(top[0][0], alias)
        uniques: dict[str, dict[tuple, dict]] = defaultdict(dict)
        for lg, d, t, dom, o, gm, gc, resolu in recs:
            a, b = uf.trouve(t), uf.trouve(o)
            dm, ex = (a, b) if dom else (b, a)
            h, g = (gm, gc) if dom else (gc, gm)
            uniques[lg][(d, dm, ex)] = {"date": d, "dom": dm, "ext": ex, "h": h, "a": g}
        self.matchs = {lg: sorted(v.values(), key=lambda m: m["date"]) for lg, v in uniques.items()}
        self._uf = uf
        self._cles = {x["cle_cache"] for x in eqs}

    def equipe(self, cle: str) -> str | None:
        return self._uf.trouve(cle) if cle in self._cles else None


def charger_ligues(chemin: Path = ASSEMBLAGE) -> Ligues:
    return Ligues(json.loads(Path(chemin).read_text(encoding="utf-8")))


# --- Matchs à pronostiquer (archive) ------------------------------------------------------------------------------
def _cle_equipe(e: dict | None, competition: Any) -> str | None:
    url = (e or {}).get("url_equipe")
    return f"{url}||{str(competition).lower()}" if url else None


def charger_archive(ligues: Ligues, dossier: Path = ARCHIVE) -> list[dict[str, Any]]:
    """Matchs de l'archive (à venir et joués), sans doublon (match_id : l'enregistrement le plus récent). Équipe sans données = match écarté.
    Un match joué n'est gardé que si ses cotes ont été prises avant le coup d'envoi."""
    vus: dict[str, dict] = {}
    for f in sorted(glob.glob(str(dossier / "*.json.gz"))):
        for k, x in json.load(gzip.open(f)).items():
            comp = x.get("competition")
            dom, ext = ligues.equipe(_cle_equipe(x.get("equipe_dom"), comp) or ""), ligues.equipe(_cle_equipe(x.get("equipe_ext"), comp) or "")
            if dom is None or ext is None:
                continue
            sc = x.get("score") or {}
            joue = sc.get("buts_dom") is not None and sc.get("buts_ext") is not None
            pris, ko = (x.get("run") or {}).get("pris_le"), x.get("coup_d_envoi_utc")
            if joue and (not pris or not ko or str(pris) >= str(ko)):
                continue
            mid = str(x.get("match_id") or f"{str(x['date'])[:10]}|{x.get('domicile')}|{x.get('exterieur')}")
            vus[mid] = {"id": mid, "ligue": str(comp).lower(), "competition": " ".join(str(comp or "").split()), "jour": str(x["date"])[:10],
                        "heure": x.get("heure_cameroun"), "coup_d_envoi_utc": ko, "domicile": x.get("domicile"), "exterieur": x.get("exterieur"),
                        "eq_dom": dom, "eq_ext": ext, "h": sc.get("buts_dom") if joue else None, "a": sc.get("buts_ext") if joue else None,
                        "cotes": x.get("cotes_betpawa") or {}}
    return sorted(vus.values(), key=lambda m: (m["jour"], m["id"]))


def nb_matchs_lieu(matchs: list[dict], equipe: str, domicile: bool, jour: str) -> int:
    """Matchs de l'équipe au lieu demandé, strictement avant `jour` (règle de Patrick : au moins 4)."""
    cle = "dom" if domicile else "ext"
    return sum(1 for m in matchs if m[cle] == equipe and m["date"] < jour)


def derniers_au_lieu(matchs: list[dict], equipe: str, domicile: bool, jour: str, n: int = 10) -> list[dict]:
    """Affichage : derniers matchs de l'équipe au même lieu (date, adversaire, buts marqués / encaissés), du plus récent au plus ancien."""
    cle, autre = ("dom", "ext") if domicile else ("ext", "dom")
    ms = [m for m in matchs if m[cle] == equipe and m["date"] < jour]
    ms.sort(key=lambda m: m["date"], reverse=True)
    return [{"date": m["date"], "adversaire": m[autre], "marques": m["h"] if domicile else m["a"], "encaisses": m["a"] if domicile else m["h"]}
            for m in ms[:n]]
