"""Bloc de saisons Football-Data pour tester les moteurs : résultats + historiques avant chaque match + cotes (évaluation seulement).

Construit à partir des CSV BRUTS déjà dans le dépôt (data/football_data/snapshots/<saison>/ et data/football_data/raw/<saison>/).
Chaque match du bloc porte : date, équipes, score, statistiques de match, et ses cotes (Bet365, Pinnacle, moyenne, maximum ;
ouverture et clôture ; 1X2, plus/moins 2,5, handicap asiatique). `entree(bloc, match)` donne à un moteur ce qui était connu
AVANT le coup d'envoi (historique strictement antérieur) : aucune fuite. Les cotes servent à juger, jamais à calculer un pronostic.
Usage : python -m matrice_scenarios.bloc_saisons [construire|resume]
"""
from __future__ import annotations

import csv
import glob
import gzip
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DOSSIER = ROOT / "data" / "bloc_saisons"
SOURCES = {  # saison -> dossiers de CSV bruts (championnats principaux, nouvelles ligues)
    "2526": ["data/football_data/snapshots/2526/raw", "data/football_data/snapshots/2526/nouvelles_ligues/raw"],
    "2627": ["data/football_data/raw/2627", "data/football_data/raw/2627/nouvelles_ligues"],
}
# (nom de sortie, colonnes CSV principaux, colonnes CSV « nouvelles ligues »)
COTES_1X2 = {"b365": ("B365H", "B365D", "B365A"), "ps": ("PSH", "PSD", "PSA"), "moy": ("AvgH", "AvgD", "AvgA"), "max": ("MaxH", "MaxD", "MaxA")}
COTES_1X2_CLOTURE = {"b365": ("B365CH", "B365CD", "B365CA"), "ps": ("PSCH", "PSCD", "PSCA"), "moy": ("AvgCH", "AvgCD", "AvgCA"), "max": ("MaxCH", "MaxCD", "MaxCA")}
COTES_OU = {"b365": ("B365>2.5", "B365<2.5"), "ps": ("P>2.5", "P<2.5"), "moy": ("Avg>2.5", "Avg<2.5"), "max": ("Max>2.5", "Max<2.5")}
COTES_OU_CLOTURE = {"b365": ("B365C>2.5", "B365C<2.5"), "ps": ("PC>2.5", "PC<2.5"), "moy": ("AvgC>2.5", "AvgC<2.5"), "max": ("MaxC>2.5", "MaxC<2.5")}
STATS = {"mt_dom": "HTHG", "mt_ext": "HTAG", "tirs_dom": "HS", "tirs_ext": "AS", "cadres_dom": "HST", "cadres_ext": "AST", "corners_dom": "HC",
         "corners_ext": "AC", "jaunes_dom": "HY", "jaunes_ext": "AY", "rouges_dom": "HR", "rouges_ext": "AR"}


def _f(x: Any) -> float | None:
    try:
        v = float(str(x).strip())
        return v if v > 1.0 else None
    except (TypeError, ValueError):
        return None


def _n(x: Any) -> float | None:
    try:
        return float(str(x).strip())
    except (TypeError, ValueError):
        return None


def date_iso(texte: str) -> str | None:
    """jj/mm/aaaa ou jj/mm/aa -> aaaa-mm-jj ; None si illisible."""
    t = str(texte).strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(t, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _groupe(row: dict, defs: dict[str, tuple[str, ...]]) -> dict[str, list[float]]:
    out = {}
    for nom, cols in defs.items():
        vals = [_f(row.get(c)) for c in cols]
        if all(v is not None for v in vals):
            out[nom] = vals
    return out


def _cotes(row: dict) -> dict[str, Any]:
    c: dict[str, Any] = {}
    for cle, defs in (("1x2_ouverture", COTES_1X2), ("1x2_cloture", COTES_1X2_CLOTURE), ("plus_moins_2_5_ouverture", COTES_OU), ("plus_moins_2_5_cloture", COTES_OU_CLOTURE)):
        g = _groupe(row, defs)
        if g:
            c[cle] = g
    ligne = _n(row.get("AHh"))
    if ligne is not None:
        ah = {n: [_f(row.get(a)), _f(row.get(b))] for n, (a, b) in {"b365": ("B365AHH", "B365AHA"), "ps": ("PAHH", "PAHA"), "moy": ("AvgAHH", "AvgAHA"), "max": ("MaxAHH", "MaxAHA")}.items()}
        ah = {k: v for k, v in ah.items() if None not in v}
        if ah:
            c["handicap_asiatique_ouverture"] = {"ligne_domicile": ligne, **ah}
    return c


def lire_csv(chemin: str, saison: str) -> list[dict[str, Any]]:
    out = []
    nouvelle = "nouvelles_ligues" in chemin
    with open(chemin, encoding="utf-8-sig", errors="replace", newline="") as fh:
        for row in csv.DictReader(fh):
            dom, ext = (row.get("Home") or row.get("HomeTeam") or "").strip(), (row.get("Away") or row.get("AwayTeam") or "").strip()
            d = date_iso(row.get("Date", ""))
            hg, ag = _n(row.get("HG") if nouvelle else row.get("FTHG")), _n(row.get("AG") if nouvelle else row.get("FTAG"))
            if not (dom and ext and d and hg is not None and ag is not None):
                continue
            code = Path(chemin).stem
            m = {"id": f"{saison}|{code}|{d}|{dom}|{ext}", "saison": saison, "division": code, "competition": (row.get("League") or row.get("Div") or code),
                 "date": d, "domicile": dom, "exterieur": ext, "buts_dom": int(hg), "buts_ext": int(ag), "cotes": _cotes(row)}
            stats = {k: _n(row.get(c)) for k, c in STATS.items()}
            m["stats"] = {k: v for k, v in stats.items() if v is not None}
            out.append(m)
    return out


def construire(saisons: list[str] | None = None) -> dict[str, Any]:
    saisons = saisons or list(SOURCES)
    matchs: list[dict[str, Any]] = []
    for s in saisons:
        for dossier in SOURCES[s]:
            for f in sorted(glob.glob(str(ROOT / dossier / "*.csv"))):
                matchs += lire_csv(f, s)
    vus, uniques = set(), []
    for m in sorted(matchs, key=lambda m: (m["date"], m["division"], m["domicile"])):
        if m["id"] not in vus:
            vus.add(m["id"])
            uniques.append(m)
    cov = defaultdict(int)
    for m in uniques:
        for k in m["cotes"]:
            cov[k] += 1
    return {"genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "saisons": saisons, "matchs": len(uniques),
            "du": uniques[0]["date"], "au": uniques[-1]["date"], "couverture_cotes": dict(cov),
            "avertissement": "Cotes réservées à l'évaluation. Saison 2425 absente du dépôt : à ajouter via archive_football_data.py (réseau requis).",
            "liste": uniques}


def ecrire(bloc: dict[str, Any]) -> Path:
    DOSSIER.mkdir(parents=True, exist_ok=True)
    p = DOSSIER / f"bloc_{'_'.join(bloc['saisons'])}.json.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        json.dump(bloc, f, ensure_ascii=False, separators=(",", ":"))
    return p


def charger(chemin: Path | None = None) -> dict[str, Any]:
    p = chemin or max(DOSSIER.glob("bloc_*.json.gz"), key=lambda x: x.stat().st_size)
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


def entree(bloc: dict[str, Any], match: dict[str, Any], n: int = 12) -> dict[str, Any]:
    """Ce qu'un moteur peut savoir AVANT le match : les `n` derniers matchs de chaque équipe (date STRICTEMENT antérieure)."""
    idx = bloc.setdefault("_index", None)
    if idx is None:
        idx = defaultdict(list)
        for m in bloc["liste"]:
            idx[m["domicile"]].append((m["date"], True, m["buts_dom"], m["buts_ext"], m["id"]))
            idx[m["exterieur"]].append((m["date"], False, m["buts_ext"], m["buts_dom"], m["id"]))
        bloc["_index"] = idx

    def avant(equipe: str) -> list[dict[str, Any]]:
        h = sorted(x for x in idx[equipe] if x[0] < match["date"])[-n:]
        return [{"date": d, "domicile": dom, "buts_marques": g, "buts_encaisses": c} for d, dom, g, c, _ in h]
    return {"id": match["id"], "date": match["date"], "competition": match["competition"], "domicile": match["domicile"],
            "exterieur": match["exterieur"], "historique_dom": avant(match["domicile"]), "historique_ext": avant(match["exterieur"])}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "construire"
    if cmd == "construire":
        b = construire()
        p = ecrire(b)
        print(p, p.stat().st_size // 1024, "Ko")
        cmd = "resume"
    if cmd == "resume":
        b = charger()
        print({k: b[k] for k in ("saisons", "matchs", "du", "au", "couverture_cotes")})
