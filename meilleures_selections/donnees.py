"""Lecture des paris gelés (avec résultat) et des sélections du jour, V2 et V3. Même sources que l'étude du 22/10/2026."""
from __future__ import annotations

import glob
import gzip
import json
import math
import os
from typing import Any

from moteur_v3.markets import gagne
from moteur_v3.model import _latest
from moteur_v3.performance import indice_performance
from v2_indice import marche_v3
from moteur_v2_6_10.noyau import artefacts_marche, categorie_value

DOSSIER_ARCHIVE = "data/archive_test"
DOSSIER_JOURNAL_V3 = "data/v3/journal"
FICHIER_V2 = "precalcul_leger.json"
FICHIER_V3 = "data/v3/pronostics_v3.json"
CATEGORIES_AFFICHEES = ("A", "B", "C")   # la catégorie D n'est jamais affichée sur la page V2
ETOILES_V2 = {"A": 3, "B": 2, "C": 1}    # traduction_marches.js : catégorie -> étoiles affichées
ETOILES_V3_NIVEAU = {"V3_ECHANTILLON_FAIBLE": 1, "V3_ECHANTILLON_UTILISABLE": 2, "V3_ECHANTILLON_SOLIDE": 3, "V3_ECHANTILLON_TRES_SOLIDE": 4}


def etoiles_v3(n_min: int) -> int:
    """moteur_v3_pipeline.niveau_echantillon : moins de 5 matchs = 1 ; 5 à 7 = 2 ; 8 à 9 = 3 ; 10 et plus = 4."""
    return 1 if n_min < 5 else 2 if n_min < 8 else 3 if n_min < 10 else 4


def pct_affiche(probabilite) -> int | None:
    """Pourcentage tel qu'affiché sur les pages (archetype_v3.js : Math.round(probabilité x 100))."""
    return int(math.floor(float(probabilite) * 100 + 0.5)) if isinstance(probabilite, (int, float)) else None


def _archive(dossier: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in sorted(glob.glob(os.path.join(dossier, "*.json.gz"))):
        for k, m in json.load(gzip.open(f)).items():
            out[str(m.get("match_id") or k)] = m
    return out


def _score(m: dict) -> tuple[int, int] | None:
    s = m.get("score") or {}
    return (s["buts_dom"], s["buts_ext"]) if isinstance(s.get("buts_dom"), int) and isinstance(s.get("buts_ext"), int) else None


def _series(m: dict, jour: str):
    return (_latest([x for x in (m.get("equipe_dom") or {}).get("matchs") or [] if str(x.get("date"))[:10] < jour], True),
            _latest([x for x in (m.get("equipe_ext") or {}).get("matchs") or [] if str(x.get("date"))[:10] < jour], False))


def paris_resolus(dossier_archive: str = DOSSIER_ARCHIVE, dossier_journal: str = DOSSIER_JOURNAL_V3) -> list[dict[str, Any]]:
    """Tous les paris V2 et V3 gelés avant le match dont le score final est connu."""
    arch = _archive(dossier_archive)
    paris: list[dict[str, Any]] = []
    dern: dict[str, dict] = {}
    for f in sorted(glob.glob(os.path.join(dossier_journal, "*.json"))):
        for mid, m in json.load(open(f, encoding="utf-8")).items():
            dern[mid] = m                                   # dernier calcul avant le coup d'envoi
    for mid, m in dern.items():
        a = arch.get(mid)
        sc = _score(a) if a else None
        if sc is None:
            continue
        for s in m.get("selections") or []:
            g = gagne(s["marche"], *sc)
            if g is None:
                continue
            dom, ext = _series(a, m["date"])
            ip = s.get("indice_performance") or indice_performance(s["marche"], dom, ext)
            nmin = min(m.get("n_dom") or len(dom), m.get("n_ext") or len(ext))
            paris.append({"moteur": "V3", "date": m["date"], "match_id": mid, "marche": s["marche"], "cote": s.get("cote"),
                          "pct": pct_affiche(s.get("probabilite")), "etoiles": etoiles_v3(nmin),
                          "indice": (ip or {}).get("indice"), "sur": (ip or {}).get("sur"), "gagne": int(g)})
    for mid, a in arch.items():
        mep = a.get("moteur_en_production") or {}
        sc = _score(a)
        if sc is None or not mep.get("choix"):
            continue
        dom, ext = _series(a, a["date"])
        version = str(mep.get("version") or "")
        for c in mep["choix"].values():
            mk3 = marche_v3(str(c.get("marche_moteur") or ""))
            g = gagne(mk3, *sc) if mk3 else None
            if g is None:
                continue
            ligne = {"marche": c["marche_moteur"], "proba_modele": c["probabilite"], "cote": c["cote"], "ev": c.get("edv") or 0.0}
            cat = categorie_value(ligne["ev"], ligne["proba_modele"], len(artefacts_marche(ligne)))
            if cat not in CATEGORIES_AFFICHEES:
                continue
            ip = indice_performance(mk3, dom, ext)
            paris.append({"moteur": "V2", "date": a["date"], "match_id": mid, "marche": mk3, "cote": c["cote"],
                          "pct": pct_affiche(c.get("probabilite")), "etoiles": ETOILES_V2[cat], "version": version,
                          "indice": (ip or {}).get("indice"), "sur": (ip or {}).get("sur"), "gagne": int(g)})
    return paris


def _charge(chemin: str) -> dict:
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def selections_du_jour(jour: str, fichier_v2: str = FICHIER_V2, fichier_v3: str = FICHIER_V3) -> list[dict[str, Any]]:
    """Sélections actuellement affichées par V2 et V3, pour les matchs de `jour` et après, au même format qu'un pari (sans résultat)."""
    out: list[dict[str, Any]] = []
    for s in _charge(fichier_v2).get("signaux") or []:
        if str(s.get("date") or "")[:10] < jour:
            continue
        sel = ((s.get("moteur_v2_6_10") or {}).get("selection")) or {}
        for rang, c in sel.items():
            if not isinstance(c, dict) or c.get("categorie") not in CATEGORIES_AFFICHEES:
                continue
            ip = c.get("indice_performance") or {}
            mk3 = marche_v3(str(c.get("marche_moteur") or ""))
            if mk3 is None:
                continue
            out.append(_ligne("V2", s, rang, c, mk3, ip))
    for s in _charge(fichier_v3).get("signaux") or []:
        if str(s.get("date") or "")[:10] < jour:
            continue
        sel = ((s.get("moteur_v3") or {}).get("selection")) or {}
        for rang, c in sel.items():
            if not isinstance(c, dict) or c.get("apercu_non_calibre"):
                continue
            out.append(_ligne("V3", s, rang, c, str(c.get("marche_moteur") or ""), c.get("indice_performance") or {}))
    return out


def _ligne(moteur: str, s: dict, rang: str, c: dict, marche3: str, ip: dict) -> dict[str, Any]:
    return {"moteur": moteur, "match_id": s.get("match_id"), "date": s.get("date"), "heure": s.get("heure_cameroun") or s.get("heure"),
            "competition": s.get("competition"), "domicile": s.get("domicile"), "exterieur": s.get("exterieur"),
            "rang_moteur": rang, "marche": marche3, "marche_affiche": c.get("marche"), "libelle": c.get("libelle"),
            "cote": c.get("cote"), "probabilite": c.get("probabilite"), "pct": pct_affiche(c.get("probabilite")),
            "etoiles": ETOILES_V2.get(c.get("categorie")) if moteur == "V2" else ETOILES_V3_NIVEAU.get(c.get("niveau")),
            "indice": ip.get("indice"), "sur": ip.get("sur")}
