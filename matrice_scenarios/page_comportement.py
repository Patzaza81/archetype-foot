"""Données de la page « Moteur alpha (ex-Comportement) » : tendances du match + pronostic principal + pronostics des autres tendances.

Lecture seule : lit data/archive_test/ (comme le moteur V3), écrit data/comportement/pronostics_comportement.json.
Rien n'est branché au pipeline, ni à V2/V3/V2R/Europe/Journal. Usage : python -m matrice_scenarios.page_comportement [--seuils]
"""
from __future__ import annotations
import re

import glob
import gzip
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from . import comportement as C
from . import scanner_marches as S
from .backtest_comportement import COTE_MIN, ROOT, historiques

PARAMS = ROOT / "docs" / "parametres_comportement.json"
SORTIE = ROOT / "data" / "comportement" / "pronostics_comportement.json"
TENDANCES = {
    "resultat": ("Résultat", ("1x2", "double_chance", "handicap", "handicap_3issues")),
    "dom_buts": ("Buts du domicile", ("over_under_domicile", "cages_inviolees_exterieur")),
    "ext_buts": ("Buts de l'extérieur", ("over_under_exterieur", "cages_inviolees_domicile")),
    "buts": ("Buts du match", ("over_under", "pair_impair", "nombre_exact_buts")),
    "deux_marquent": ("Les deux marquent", ("btts",)),
}


def tendance_de(groupe: str) -> str | None:
    from .recalage import famille
    f = famille(groupe)
    return next((k for k, (_, fams) in TENDANCES.items() if f in fams), None)


def evenement(groupe: str, selection: str, n: int = C.GRID) -> frozenset | None:
    """Ensemble des scores qui font gagner la sélection : deux sélections au même ensemble sont le MÊME événement (ex. « domicile
    plus de 0,5 » et « cage de l'extérieur non inviolée »)."""
    t = S.test_du_marche(groupe, selection)
    return frozenset((i, j) for i in range(n) for j in range(n) if t(i, j)) if t else None


def _fr(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def tendances_du_match(prof: dict[str, Any], dom: str, ext: str, p: dict[str, float]) -> list[dict[str, str]]:
    """`texte` : version chiffrée (détails). `court` : une phrase pour le parieur (absente quand il n'y a pas de tendance à signaler)."""
    out = []
    pc = lambda x: f"{round(100 * x)} %"
    if prof["favori"] == "domicile":
        out.append({"cle": "resultat", "titre": "Résultat", "court": f"{dom} favori ({pc(prof['victoire_dom'])})",
                    "texte": f"{dom} favori : {pc(prof['victoire_dom'])} de victoire contre {pc(prof['victoire_ext'])}."})
    elif prof["favori"] == "extérieur":
        out.append({"cle": "resultat", "titre": "Résultat", "court": f"{ext} favori ({pc(prof['victoire_ext'])})",
                    "texte": f"{ext} favori : {pc(prof['victoire_ext'])} de victoire contre {pc(prof['victoire_dom'])}."})
    else:
        out.append({"cle": "resultat", "titre": "Résultat", "court": "Match serré, pas de favori net",
                    "texte": f"Match équilibré : {dom} {pc(prof['victoire_dom'])} · nul {pc(prof['nul'])} · {ext} {pc(prof['victoire_ext'])}."})
    g = prof["grille"]
    for cle, nom, idx in (("dom_buts", dom, 0), ("ext_buts", ext, 1)):
        marg = [sum(row[k] for row in g) if idx else sum(g[k]) for k in range(len(g))]
        d = [marg[0], marg[1], marg[2], sum(marg[3:])]
        meilleur = max(range(4), key=lambda k: d[k])
        lib = ["aucun but", "1 but", "2 buts", "3 buts ou plus"][meilleur]
        nette = d[meilleur] >= p["seuil_buts_equipe"]
        entree = {"cle": cle, "titre": f"Buts de {nom}", "nette": nette,
                  "texte": (f"{lib} le plus probable ({pc(d[meilleur])})" if nette else "Pas de tendance nette") + f" · 0 but {pc(d[0])} · 2 buts ou plus {pc(d[2] + d[3])}."}
        if nette:
            entree["court"] = f"{nom} : {lib} probable ({pc(d[meilleur])})"
        out.append(entree)
    if prof["buts"] != "équilibré":
        ouvert = prof["buts"] == "offensif"
        out.append({"cle": "buts", "titre": "Buts du match",
                    "court": ("Match ouvert : beaucoup de buts" if ouvert else "Match fermé : peu de buts") + f" ({_fr(prof['total_attendu'])} attendus)",
                    "texte": f"Match {prof['buts']} : {_fr(prof['total_attendu'])} buts attendus."})
    if prof["deux_marquent"] >= p["seuil_btts_haut"]:
        out.append({"cle": "deux_marquent", "titre": "Les deux marquent", "court": "Les deux équipes marquent souvent",
                    "texte": "Les deux équipes marquent souvent dans les séries croisées."})
    elif prof["deux_marquent"] <= p["seuil_btts_bas"]:
        out.append({"cle": "deux_marquent", "titre": "Les deux marquent", "court": "Une équipe risque de ne pas marquer",
                    "texte": "Une des deux équipes risque de ne pas marquer."})
    if prof["scores_extremes"]:
        out.append({"cle": "extremes", "titre": "Scores extrêmes", "texte": "Séries avec un score extrême : " + ", ".join(prof["scores_extremes"][:3]) + "."})
    return out


def libelle_parieur(groupe: str, selection: str, dom: str, ext: str, defaut: str) -> str:
    """Intitulé du marché tel qu'on le lit sur un coupon : les équipes par leur nom."""
    s = str(selection)
    if groupe == "1x2":
        return {"1": f"{dom} gagne", "N": "Match nul", "2": f"{ext} gagne"}.get(s, defaut)
    if groupe == "double_chance":
        return {"1N": f"{dom} ne perd pas (1N)", "N2": f"{ext} ne perd pas (N2)", "12": "Pas de match nul (12)"}.get(s, defaut)
    m = re.fullmatch(r"handicap_(-?\d+(?:\.\d+)?)", groupe)
    if m and s in ("domicile", "exterieur"):
        h = float(m.group(1)) if s == "domicile" else -float(m.group(1))
        return f"{dom if s == 'domicile' else ext} {format(h, '+g').replace('.', ',')} (handicap)"
    m = re.fullmatch(r"handicap_3issues_(-?\d+)", groupe)
    if m and s in ("1", "X", "2"):
        k = int(m.group(1))
        return {"1": f"{dom} {k:+d} (handicap 3 issues)", "X": f"Nul avec handicap {k:+d} sur {dom}", "2": f"{ext} {-k:+d} (handicap 3 issues)"}[s]
    return defaut


def analyser_match(m: dict[str, Any], p: dict[str, Any], collecte: list | None = None) -> dict[str, Any]:
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
    vus = {evenement(principal["groupe"], principal["selection"])}
    for t in tend:
        cle = t["cle"]
        if cle not in TENDANCES or principal["tendance"] == cle or t.get("nette") is False:
            continue
        seuil = p.get("seuils_tendance", {}).get(cle, p["seuil_secondaire"])
        cand = [x for x in eligibles if x["tendance"] == cle and evenement(x["groupe"], x["selection"]) not in vus]
        if not cand:
            continue
        meilleur = max(cand, key=lambda x: (round(x["probabilite"], 6), x["cote"]))
        if collecte is not None and m.get("score_final"):
            collecte.append({"date": m["date"], "tendance": cle, "probabilite": meilleur["probabilite"],
                             "gagne": bool(S.test_du_marche(meilleur["groupe"], meilleur["selection"])(m["score_final"]["buts_dom"], m["score_final"]["buts_ext"]))})
        if meilleur["probabilite"] >= seuil:
            vus.add(evenement(meilleur["groupe"], meilleur["selection"]))
            choix.append(dict(meilleur, role="tendance"))
    sel = []
    for i, c in enumerate(choix, 1):
        s = {"rang": i, "role": c["role"], "tendance": TENDANCES.get(c["tendance"] or "", ("Autre",))[0], "libelle": libelle_parieur(c["groupe"], c["selection"], m["domicile"], m["exterieur"], c["libelle"]), "cote": c["cote"],
             "probabilite": round(c["probabilite"], 3), "groupe": c["groupe"], "choix": c["selection"]}
        if m.get("score_final"):
            s["gagne"] = bool(S.test_du_marche(c["groupe"], c["selection"])(m["score_final"]["buts_dom"], m["score_final"]["buts_ext"]))
        sel.append(s)
    return {**base, "statut": "OK", "selections": sel}


def charger_matchs() -> list[dict[str, Any]]:
    out = []
    dossier = os.environ.get("COMPORTEMENT_ARCHIVE") or str(ROOT / "data" / "archive_test")     # variable : lire l'archive d'une autre copie (ex. main)
    for f in sorted(glob.glob(str(Path(dossier) / "*.json.gz"))):
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
    valeurs, ecarts, modales = [], [], []
    for r in sorted(fd, key=lambda r: r["date"])[: int(len(fd) * 0.6) : 3]:
        d = [(x["goals_for"], x["goals_against"]) for x in sorted([x for x in r["home_history"] if x["venue"] == "home" and str(x["date"])[:10] < r["date"]], key=lambda x: x["date"])[C.DEBUT:]]
        e = [(x["goals_for"], x["goals_against"]) for x in sorted([x for x in r["away_history"] if x["venue"] == "away" and str(x["date"])[:10] < r["date"]], key=lambda x: x["date"])[C.DEBUT:]]
        if len(d) >= 3 and len(e) >= 3:
            g = C.grille(*C.buts_attendus(d, e), C.RHO)
            valeurs.append(C.proba(g, lambda i, j: i >= 1 and j >= 1))
            ecarts.append(abs(C.proba(g, lambda i, j: i > j) - C.proba(g, lambda i, j: i < j)))
            for idx in (0, 1):
                marg = [sum(row[k] for row in g) if idx else sum(g[k]) for k in range(len(g))]
                d4 = [marg[0], marg[1], marg[2], sum(marg[3:])]
                modales.append(max(d4))
    modales.sort()
    valeurs.sort()
    ecarts.sort()
    probs = sorted(p["probabilite"] for m in charger_archive() if (p := pick(m, None)))
    seuil_equipe = modales[2 * len(modales) // 3]
    # validation sur les 40 % de Football-Data jamais utilisés : la classe la plus probable sort-elle plus souvent au-dessus du seuil ?
    hors = {"au_dessus": [0, 0], "en_dessous": [0, 0]}
    for r in sorted(fd, key=lambda r: r["date"])[int(len(fd) * 0.6):]:
        d = [(x["goals_for"], x["goals_against"]) for x in sorted([x for x in r["home_history"] if x["venue"] == "home" and str(x["date"])[:10] < r["date"]], key=lambda x: x["date"])[C.DEBUT:]]
        e = [(x["goals_for"], x["goals_against"]) for x in sorted([x for x in r["away_history"] if x["venue"] == "away" and str(x["date"])[:10] < r["date"]], key=lambda x: x["date"])[C.DEBUT:]]
        if len(d) < 3 or len(e) < 3:
            continue
        g = C.grille(*C.buts_attendus(d, e), C.RHO)
        for idx, reel in ((0, r["home_goals"]), (1, r["away_goals"])):
            marg = [sum(row[k] for row in g) if idx else sum(g[k]) for k in range(len(g))]
            d4 = [marg[0], marg[1], marg[2], sum(marg[3:])]
            m = max(range(4), key=lambda k: d4[k])
            cl = min(reel, 3)
            h = hors["au_dessus" if d4[m] >= seuil_equipe else "en_dessous"]
            h[0] += 1
            h[1] += int(cl == m)
    P.update({"seuil_buts_equipe": seuil_equipe,
              "validation_seuil_buts_equipe": {k: {"cas": v[0], "classe_la_plus_probable_sortie": round(v[1] / v[0], 3)} for k, v in hors.items()},
              "seuil_btts_bas": valeurs[len(valeurs) // 3], "seuil_btts_haut": valeurs[2 * len(valeurs) // 3],
              "seuil_secondaire": probs[len(probs) // 4], "seuil_ecart_favori": ecarts[2 * len(ecarts) // 3], "seuils_page": "tertiles BTTS (Football-Data) ; quartile bas des pronostics principaux (archive)"})
    PARAMS.write_text(json.dumps(P, ensure_ascii=False, indent=1), encoding="utf-8")
    print({k: round(P[k], 3) for k in ("seuil_btts_bas", "seuil_btts_haut", "seuil_secondaire", "seuil_ecart_favori", "seuil_buts_equipe")}, P["validation_seuil_buts_equipe"])


def calculer_seuils_tendances() -> dict:
    """Seuil par tendance mesuré sur la 1re moitié des matchs joués de l'archive : la plus petite probabilité à partir de laquelle les
    pronostics de cette tendance ont réussi AU MOINS AUTANT que les pronostics principaux (même moitié), sur 40 cas minimum.
    Sans tel seuil, la tendance ne propose pas de pronostic secondaire. Jugé ensuite sur la 2e moitié (jamais vue)."""
    P = json.loads(PARAMS.read_text(encoding="utf-8"))
    P.pop("seuils_tendance", None)
    coll: list = []
    principaux: list = []
    for m in charger_matchs():
        r = analyser_match(m, {**P, "seuil_secondaire": 0.0}, coll)
        if r["selections"] and "gagne" in r["selections"][0]:
            principaux.append((m["date"], r["selections"][0]["gagne"]))
    jours = sorted(c["date"] for c in coll)
    coupe = jours[len(jours) // 2]
    cible = sum(g for d, g in principaux if d < coupe) / sum(1 for d, g in principaux if d < coupe)
    seuils, verif = {}, {"cible_principaux_apprentissage": round(cible, 3), "jour_de_coupe": coupe}
    for cle in TENDANCES:
        app = sorted((c for c in coll if c["tendance"] == cle and c["date"] < coupe), key=lambda c: -c["probabilite"])
        seuil, gagnes = None, 0
        for i, c in enumerate(app, 1):                       # du plus probable au moins probable
            gagnes += c["gagne"]
            if i >= 40 and gagnes / i >= cible:
                seuil = c["probabilite"]
        te = [c for c in coll if c["tendance"] == cle and c["date"] >= coupe]
        seuils[cle] = seuil if seuil is not None else 2.0    # 2,0 : aucun pronostic secondaire pour cette tendance
        au = [c for c in te if c["probabilite"] >= seuils[cle]]
        verif[cle] = {"seuil": None if seuil is None else round(seuil, 3), "apprentissage": len(app),
                      "test": {"cas": len(au), "reussite": round(sum(c["gagne"] for c in au) / len(au), 3) if au else None}}
    P["seuils_tendance"], P["validation_seuils_tendance"] = seuils, verif
    PARAMS.write_text(json.dumps(P, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(verif, ensure_ascii=False, indent=1))
    return verif


def construire() -> dict[str, Any]:
    p = json.loads(PARAMS.read_text(encoding="utf-8"))
    matchs = [analyser_match(m, p) for m in charger_matchs()]
    perf = json.loads((ROOT / "docs" / "recalage_familles.json").read_text(encoding="utf-8"))["resultats_archive"]["sans_recalage"]
    sec = [x for m in matchs for x in m["selections"] if x["role"] == "tendance" and "gagne" in x]
    secondaires = {"matchs": len(sec), "reussite": round(sum(x["gagne"] for x in sec) / len(sec), 4)} if sec else None
    return {"moteur": "comportement", "statut": "OK", "genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "promotion_allowed": False, "cote_min": COTE_MIN,
            "performance_archive": {"matchs": perf["n"], "reussite": perf["reussite"], "ic95": perf["ic95_jours"], "annonce_moyenne": perf["annonce"],
                                    "note": "La probabilité du modèle est surestimée d'environ 10 points : se fier à la réussite mesurée."},
            "seuil_secondaire": p["seuil_secondaire"], "pronostics_autres_tendances_archive": secondaires, "matchs": matchs}


def ecrire_page() -> dict[str, Any]:
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    d = construire()
    SORTIE.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return d


if __name__ == "__main__":
    if "--seuils" in sys.argv:
        calculer_seuils()
        calculer_seuils_tendances()
    d = ecrire_page()
    ok = sum(m["statut"] == "OK" for m in d["matchs"])
    print(len(d["matchs"]), "matchs,", ok, "avec pronostic,", sum(len(m["selections"]) for m in d["matchs"]), "sélections")
