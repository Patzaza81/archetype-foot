"""Données de MEGAPOWER v2 : matchs du flux commun (data/archive_test) avec l'historique des deux équipes, et scores connus.

Aucune cote n'est lue. Seul ce qui était connu AVANT le coup d'envoi entre dans un match (règle anti-fuite de l'archive : aucun match d'équipe daté du jour du match ou après).
Un xG manquant reste manquant (jamais inventé) : l'observation est alors lue sur les buts seulement.
"""
from __future__ import annotations

import glob
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FLUX = ROOT / "data" / "archive_test"


def scores() -> dict[str, tuple[int, int]]:
    out = {}
    for j in json.loads((ROOT / "historique_pronostics.json").read_text(encoding="utf-8")):
        for m in j["matchs"]:
            if re.fullmatch(r"\d+-\d+", str(m.get("score"))):
                out[m["match_id"]] = tuple(map(int, m["score"].split("-")))
    return out


def _records(equipe: dict | None, saison: str | None, jour: str) -> list[dict]:
    """Matchs de la saison en cours d'une équipe, strictement avant `jour`, triés par date. Champs : date, dom, adv, gf, ga, xgf, xga (None si absents)."""
    out, vus = [], set()
    for m in (equipe or {}).get("matchs") or []:
        d = str(m.get("date") or "")[:10]
        if not d or d >= jour or m.get("provisoire") or d in vus:
            continue
        if saison and m.get("saison") and m["saison"] != saison:
            continue
        if not isinstance(m.get("buts_marques"), int) or not isinstance(m.get("buts_encaisses"), int) or m.get("domicile") is None:
            continue
        vus.add(d)
        ok = isinstance(m.get("xg"), (int, float)) and isinstance(m.get("xg_concede"), (int, float))
        out.append({"date": d, "dom": bool(m["domicile"]), "adv": m.get("adversaire"), "gf": m["buts_marques"], "ga": m["buts_encaisses"],
                    "xgf": float(m["xg"]) if ok else None, "xga": float(m["xg_concede"]) if ok else None})
    return sorted(out, key=lambda r: r["date"])


def lire_flux(jour_min: str | None = None) -> list[dict]:
    """Un enregistrement par match (dernière apparition dans le flux), trié par jour. Les matchs sans historique exploitable des deux équipes sont écartés."""
    par_id: dict[str, dict] = {}
    for f in sorted(glob.glob(str(FLUX / "*.json.gz"))):
        if jour_min and Path(f).name[:10] < jour_min:
            continue
        for k, x in json.load(gzip.open(f)).items():
            a = x.get("assemblage") or {}
            if a.get("statut") != "OK" or not x.get("date"):
                continue
            ed, ee = a.get("equipe_dom") or {}, a.get("equipe_ext") or {}
            if ed.get("statut") != "OK" or ee.get("statut") != "OK":
                continue
            saison = a.get("saison_football_data")
            par_id[k] = {"id": k, "jour": x["date"], "ko": x.get("coup_d_envoi_utc"), "competition": x.get("competition"), "saison": saison,
                         "domicile": x.get("domicile"), "exterieur": x.get("exterieur"), "heure": x.get("heure_cameroun"),
                         "cle_dom": ed.get("nom_football_data") or x.get("domicile"), "cle_ext": ee.get("nom_football_data") or x.get("exterieur"),
                         "md": _records(ed, saison, x["date"]), "me": _records(ee, saison, x["date"])}
    return sorted(par_id.values(), key=lambda m: (m["jour"], m["id"]))
