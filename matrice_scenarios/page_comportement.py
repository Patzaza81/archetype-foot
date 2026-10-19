"""Données de la page « Moteur Comportement » : tendances du match + pronostic principal + pronostics des autres tendances.

Lecture seule : lit data/archive_test/ (comme le moteur V3), écrit data/comportement/pronostics_comportement.json.
Rien n'est branché au pipeline, ni à V2/V3/V2R/Europe/Journal. Usage : python -m matrice_scenarios.page_comportement [--seuils]
"""
from __future__ import annotations

import glob
import gzip
import json
import sys
from datetime import datetime, timezone
from typing import Any

from . import comportement as C
from . import scanner_marches as S
from .backtest_comportement import COTE_MIN, ROOT, historiques

PARAMS = ROOT / "docs" / "parametres_comportement.json"
SORTIE = ROOT / "data" / "comportement" / "pronostics_comportement.json"
TENDANCES = {
    "resultat": ("Résultat", ("1x2", "double_chance", "handicap", "handicap_3issues")),
    "buts": ("Buts du match", ("over_under", "over_under_domicile", "over_under_exterieur", "pair_impair", "nombre_exact_buts")),
    "deux_marquent": ("Les deux marquent", ("btts", "cages_inviolees_domicile", "cages_inviolees_exterieur")),
}


def tendance_de(groupe: str) -> str | None:
    from .recalage import famille
    f = famille(groupe)
    return next((k for k, (_, fams) in TENDANCES.items() if f in fams), None)


def _fr(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def tendances_du_match(prof: dict[str, Any], dom: str, ext: str, p: dict[str, float]) -> list[dict[str, str]]:
    out = []
    pc = lambda x: f"{round(100 * x)} %"
    if prof["favori"] == "domicile":
        out.append({"cle": "resultat", "titre": "Résultat", "texte": f"{dom} favori : {pc(prof['victoire_dom'])} de victoire contre {pc(prof['victoire_ext'])}."})
    elif prof["favori"] == "extérieur":
        out.append({"cle": "resultat", "titre": "Résultat", "texte": f"{ext} favori : {pc(prof['victoire_ext'])} de victoire contre {pc(prof['victoire_dom'])}."})
    else:
        out.append({"cle": "resultat", "titre": "Résultat", "texte": f"Match équilibré : {dom} {pc(prof['victoire_dom'])} · nul {pc(prof['nul'])} · {ext} {pc(prof['victoire_ext'])}."})
    if prof["buts"] != "équilibré":
        out.append({"cle": "buts", "titre": "Buts du match", "texte": f"Match {prof['buts']} : {_fr(prof['total_attendu'])} buts attendus."})
    if prof["deux_marquent"] >= p["seuil_btts_haut"]:
        out.append({"cle": "deux_marquent", "titre": "Les deux marquent", "texte": "Les deux équipes marquent souvent dans les séries croisées."})
    elif prof["deux_marquent"] <= p["seuil_btts_bas"]:
        out.append({"cle": "deux_marquent", "titre": "Les deux marquent", "texte": "Une des deux équipes risque de ne pas marquer."})
    if prof["scores_extremes"]:
        out.append({"cle": "extremes", "titre": "Scores extrêmes", "texte": "Séries avec un score extrême : " + ", ".join(prof["scores_extremes"][:3]) + "."})
    return out


def analyser_match(m: dict[str, Any], p: dict[str, float]) -> dict[str, Any]:
    base = {"match_id": m["match_id"], "date": m["date"], "heure": m.get("heure_cameroun"), "competition": m.get("competition"),
            "domicile": m["domicile"], "exterieur": m["exterieur"], "score": m.get("score_final"), "selections": [], "tendances": []}
    a = m.get("assemblage") or {}
    h = historiques(a["equipe_dom"], a["equipe_ext"], m["date"]) if "matchs" in (a.get("equipe_dom") or {}) and "matchs" in (a.get("equipe_ext") or {}) else None
    if not h:
        return {**base, "statut": "NON_EVALUE : HISTORIQUE_INSUFFISANT"}
    if not m.get("cotes_betpawa"):
        return {**base, "statut": "NON_EVALUE : COTES_ABSENTES"}
    dom, ext = h
    prof = C.profil(dom, ext)
    marches, non_lus = S.scanner(prof["grille"], m["cotes_betpawa"])
    for x in marches:
        x["tendance"] = tendance_de(x["groupe"])
    eligibles = [x for x in marches if x["cote"] >= COTE_MIN]
    principal = S.choisir(marches, COTE_MIN)
    tend = tendances_du_match(prof, m["domicile"], m["exterieur"], p)
    base.update({"tendances": tend, "profil": {k: prof[k] for k in ("buts_attendus", "total_attendu", "victoire_dom", "nul", "victoire_ext", "favori", "buts", "deux_marquent")},
                 "series": {"domicile": len(dom), "exterieur": len(ext)}, "non_lus": non_lus})
    if not principal:
        return {**base, "statut": "AUCUN_MARCHE_COTE_1_26"}
    choix = [dict(principal, role="principal")]
    for cle in [t["cle"] for t in tend if t["cle"] in TENDANCES]:
        cand = [x for x in eligibles if x["tendance"] == cle and x["probabilite"] >= p["seuil_secondaire"] and (x["groupe"], x["selection"]) != (principal["groupe"], principal["selection"])]
        if cand and principal["tendance"] != cle:
            choix.append(dict(max(cand, key=lambda x: (round(x["probabilite"], 6), x["cote"])), role="tendance"))
    sel = []
    for i, c in enumerate(choix[:3], 1):
        s = {"rang": i, "role": c["role"], "tendance": TENDANCES.get(c["tendance"] or "", ("Autre",))[0], "libelle": c["libelle"], "cote": c["cote"],
             "probabilite": round(c["probabilite"], 3), "groupe": c["groupe"], "choix": c["selection"]}
        if m.get("score_final"):
            s["gagne"] = bool(S.test_du_marche(c["groupe"], c["selection"])(m["score_final"]["buts_dom"], m["score_final"]["buts_ext"]))
        sel.append(s)
    return {**base, "statut": "OK", "selections": sel}


def charger_matchs() -> list[dict[str, Any]]:
    out = []
    for f in sorted(glob.glob(str(ROOT / "data" / "archive_test" / "*.json.gz"))):
        for x in json.load(gzip.open(f)).values():
            sc = x.get("score") or {}
            x["score_final"] = {"buts_dom": sc["buts_dom"], "buts_ext": sc["buts_ext"]} if sc.get("buts_dom") is not None else None
            out.append(x)
    return out


def calculer_seuils() -> None:
    """Seuils mesurés (jamais posés) : tertiles de « les deux marquent » sur Football-Data, et seuil des pronostics secondaires =
    probabilité du quart le plus faible des pronostics principaux de l'archive jouée."""
    from .backtest_comportement import charger_archive, pick
    from .football_data import load_football_data
    P = json.loads(PARAMS.read_text(encoding="utf-8"))
    fd, _ = load_football_data()
    valeurs, ecarts = [], []
    for r in sorted(fd, key=lambda r: r["date"])[: int(len(fd) * 0.6) : 3]:
        d = [(x["goals_for"], x["goals_against"]) for x in sorted([x for x in r["home_history"] if x["venue"] == "home" and str(x["date"])[:10] < r["date"]], key=lambda x: x["date"])[-5:]]
        e = [(x["goals_for"], x["goals_against"]) for x in sorted([x for x in r["away_history"] if x["venue"] == "away" and str(x["date"])[:10] < r["date"]], key=lambda x: x["date"])[-5:]]
        if len(d) >= 3 and len(e) >= 3:
            g = C.grille(*C.buts_attendus(d, e), C.RHO)
            valeurs.append(C.proba(g, lambda i, j: i >= 1 and j >= 1))
            ecarts.append(abs(C.proba(g, lambda i, j: i > j) - C.proba(g, lambda i, j: i < j)))
    valeurs.sort()
    ecarts.sort()
    probs = sorted(p["probabilite"] for m in charger_archive() if (p := pick(m, None)))
    P.update({"seuil_btts_bas": valeurs[len(valeurs) // 3], "seuil_btts_haut": valeurs[2 * len(valeurs) // 3],
              "seuil_secondaire": probs[len(probs) // 4], "seuil_ecart_favori": ecarts[2 * len(ecarts) // 3], "seuils_page": "tertiles BTTS (Football-Data) ; quartile bas des pronostics principaux (archive)"})
    PARAMS.write_text(json.dumps(P, ensure_ascii=False, indent=1), encoding="utf-8")
    print({k: round(P[k], 3) for k in ("seuil_btts_bas", "seuil_btts_haut", "seuil_secondaire", "seuil_ecart_favori")})


def construire() -> dict[str, Any]:
    p = json.loads(PARAMS.read_text(encoding="utf-8"))
    matchs = [analyser_match(m, p) for m in charger_matchs()]
    perf = json.loads((ROOT / "docs" / "recalage_familles.json").read_text(encoding="utf-8"))["resultats_archive"]["sans_recalage"]
    return {"moteur": "comportement", "statut": "OK", "genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "promotion_allowed": False, "cote_min": COTE_MIN,
            "performance_archive": {"matchs": perf["n"], "reussite": perf["reussite"], "ic95": perf["ic95_jours"], "annonce_moyenne": perf["annonce"],
                                    "note": "La probabilité du modèle est surestimée d'environ 10 points : se fier à la réussite mesurée."},
            "seuil_secondaire": p["seuil_secondaire"], "matchs": matchs}


if __name__ == "__main__":
    if "--seuils" in sys.argv:
        calculer_seuils()
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    d = construire()
    SORTIE.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    ok = sum(m["statut"] == "OK" for m in d["matchs"])
    print(len(d["matchs"]), "matchs,", ok, "avec pronostic,", sum(len(m["selections"]) for m in d["matchs"]), "sélections")
