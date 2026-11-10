"""Base d'apprentissage de MEGAPOWER : tous les matchs joués du flux commun (cotes Betpawa + historiques + score), un signal par moteur et par marché."""
from __future__ import annotations

import glob
import gzip
import json
import os
import re
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

import verif_pronostic as V
from . import signaux as S

ROOT = Path(__file__).resolve().parent.parent
FLUX = ROOT / "data" / "archive_test"


def scores() -> dict[str, tuple[int, int]]:
    out = {}
    for j in json.loads((ROOT / "historique_pronostics.json").read_text(encoding="utf-8")):
        for m in j["matchs"]:
            if re.fullmatch(r"\d+-\d+", str(m.get("score"))):
                out[m["match_id"]] = tuple(map(int, m["score"].split("-")))
    return out


def _fichier(f: str) -> list[dict]:
    cfg = V.config()
    out = []
    for k, x in json.load(gzip.open(f)).items():
        if not x.get("cotes_betpawa") or not x.get("date"):
            continue
        try:
            r = S.lire(x, cfg)
        except Exception:                                   # noqa: BLE001 : un match illisible n'arrête pas la base
            r = None
        if r is None:
            continue
        out.append({"id": k, "jour": x["date"], "ko": x.get("coup_d_envoi_utc"), "competition": x.get("competition"), "domicile": x.get("domicile"), "exterieur": x.get("exterieur"),
                    "heure": x.get("heure_cameroun"), **r})
    return out


def lire_flux(jour_min: str | None = None, jour_max: str | None = None) -> list[dict]:
    """Un enregistrement par match (dernière apparition dans le flux)."""
    fichiers = [f for f in sorted(glob.glob(str(FLUX / "*.json.gz"))) if (not jour_min or os.path.basename(f)[:10] >= jour_min) and (not jour_max or os.path.basename(f)[:10] <= jour_max)]
    par_id: dict[str, dict] = {}
    with ProcessPoolExecutor(max_workers=min(8, os.cpu_count() or 2)) as ex:
        for lot in ex.map(_fichier, fichiers):
            for m in lot:
                par_id[m["id"]] = m
    return sorted(par_id.values(), key=lambda m: (m["jour"], m["id"]))


def tableau(matchs: list[dict], sc: dict[str, tuple[int, int]] | None = None) -> dict[str, np.ndarray]:
    """Lignes (match, marché coté) : signaux, cote, résultat (NaN si le match n'est pas joué)."""
    sc = scores() if sc is None else sc
    L = {k: [] for k in ("match", "marche", "cote", "y", *S.SIGNAUX)}
    for t, m in enumerate(matchs):
        idx = np.nonzero(~np.isnan(m["cote"]))[0]
        s = sc.get(m["id"])
        L["match"].append(np.full(len(idx), t)); L["marche"].append(idx); L["cote"].append(m["cote"][idx])
        L["y"].append(S.TABLE[min(s[0], S.CAP), min(s[1], S.CAP), idx].astype(float) if s else np.full(len(idx), np.nan))
        for k in S.SIGNAUX:
            L[k].append(m["signaux"][k][idx])
    return {k: np.concatenate(v) if v else np.array([]) for k, v in L.items()}
