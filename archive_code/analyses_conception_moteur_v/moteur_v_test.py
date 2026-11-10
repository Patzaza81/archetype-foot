#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Moteur « v » (prototype de test) -- règles FIGÉES avant le test, jamais réglées sur les résultats.

Entrées : data/archive_test/*.json.gz (cotes observées, historiques des deux équipes, score final).
Sortie  : chiffres bruts (aucun fichier du dépôt n'est modifié).

Règles (décidées par Patrick) :
  - >= 4 matchs au même lieu pour les deux équipes, sinon match exclu ; fenêtre = 12 derniers matchs.
  - k : 4 matchs = 0,8 ; 5 matchs = 0,9 ; 6 et plus = 1,0 (échantillon le plus court des deux équipes).
  - pourcentage final = pourcentage brut (fréquence réelle) x k.
  - verrou d'échantillon : 75 % (4-5 matchs) / 72 % (6 et plus) ; seuil de cote : 77 % pour 1,26-1,37, 72 % au-dessus ;
    le pari doit passer les deux (le plus exigeant des deux).
  - cote minimale 1,26 ; un seul pari par match (plus haut pourcentage final, à égalité la cote la plus haute).
Choix de lecture ajoutés par Claude (à valider) : pourcentage brut = moyenne des deux taux (un par équipe, au même lieu) ;
  variante « min » = chaque côté doit passer seul ; musique/pics/ruptures = ALERTES affichées, jamais des filtres.
"""
import glob
import gzip
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict

FENETRE = 12
MIN_MATCHS = 4
COTE_MIN = 1.26
COTE_BORNE = 1.37
SEUIL_ZONE_BASSE = 0.77
SEUIL_BASE = 0.72
VERROU_PETIT = 0.75
VERROU_GRAND = 0.72
MARGE_SURVEILLER = 0.05
EPS = 1e-9


def coef_k(n):
    if n < MIN_MATCHS:
        return None
    return {4: 0.8, 5: 0.9}.get(n, 1.0)


def verrou(n):
    return VERROU_PETIT if n <= 5 else VERROU_GRAND


def seuil_cote(cote):
    if cote < COTE_MIN:
        return None
    return SEUIL_ZONE_BASSE if cote <= COTE_BORNE else SEUIL_BASE


def seuil_pari(n_min, cote):
    sc = seuil_cote(cote)
    if sc is None:
        return None
    return max(verrou(n_min), sc)


def decide(raw, n_min, cote):
    """True si le pari passe (pourcentage final = raw x k, seuils de verrou ET de cote)."""
    k = coef_k(n_min)
    s = seuil_pari(n_min, cote) if k is not None else None
    if s is None:
        return False
    return raw * k >= s - EPS


# ------------------------------------------------------------------ marchés
_NUM = r"(-?\d+(?:\.\d+)?)"


def market_def(key):
    """Retourne (predicat(h,a), serie) ou None. h = buts du domicile, a = buts de l'extérieur du MATCH."""
    m = re.fullmatch(r"1X2 - (1|X|2)", key)
    if m:
        s = m.group(1)
        return ({"1": lambda h, a: h > a, "X": lambda h, a: h == a, "2": lambda h, a: h < a}[s], "diff")
    m = re.fullmatch(r"Double chance - (1X|X2|12)", key)
    if m:
        s = m.group(1)
        return ({"1X": lambda h, a: h >= a, "X2": lambda h, a: h <= a, "12": lambda h, a: h != a}[s], "diff")
    m = re.fullmatch(r"BTTS - (oui|non)", key)
    if m:
        oui = m.group(1) == "oui"
        return ((lambda h, a: (h > 0 and a > 0) == oui), "btts")
    m = re.fullmatch(r"(Plus|Moins) de " + _NUM + r" buts - (Domicile|Extérieur)", key)
    if m:
        x, over, dom = float(m.group(2)), m.group(1) == "Plus", m.group(3) == "Domicile"
        if dom:
            return ((lambda h, a: h > x) if over else (lambda h, a: h < x), "h")
        return ((lambda h, a: a > x) if over else (lambda h, a: a < x), "a")
    m = re.fullmatch(r"(Plus|Moins) de " + _NUM + r" buts", key)
    if m:
        x, over = float(m.group(2)), m.group(1) == "Plus"
        return ((lambda h, a: h + a > x) if over else (lambda h, a: h + a < x), "total")
    m = re.fullmatch(r"Handicap " + _NUM + r" - (Domicile|Extérieur)", key)
    if m:
        x, dom = float(m.group(1)), m.group(2) == "Domicile"
        if abs(x) > 1.5:  # handicaps extrêmes exclus
            return None
        return ((lambda h, a: h + x > a) if dom else (lambda h, a: h + x < a), "diff")
    m = re.fullmatch(r"Cage inviolée - (Domicile|Extérieur)", key)
    if m:
        return ((lambda h, a: a == 0) if m.group(1) == "Domicile" else (lambda h, a: h == 0),
                "a" if m.group(1) == "Domicile" else "h")
    m = re.fullmatch(r"Encaisse au moins \d+ but - (Domicile|Extérieur)", key)
    if m:
        return ((lambda h, a: a >= 1) if m.group(1) == "Domicile" else (lambda h, a: h >= 1),
                "a" if m.group(1) == "Domicile" else "h")
    return None  # pair/impair et le reste : non lus


def famille(key):
    if key.startswith("1X2"):
        return "1X2"
    if key.startswith("Double chance"):
        return "Double chance"
    if key.startswith("BTTS"):
        return "BTTS"
    if key.startswith("Handicap"):
        return "Handicap"
    if key.startswith("Cage") or key.startswith("Encaisse"):
        return "Cage / encaisse"
    if " - Domicile" in key or " - Extérieur" in key:
        return "Buts d'une équipe"
    return "Total buts"


# ------------------------------------------------------------------ musique (alertes)
def serie_valeurs(rows, serie):
    out = []
    for h, a in rows:
        out.append({"diff": h - a, "total": h + a, "h": h, "a": a, "btts": int(h > 0 and a > 0)}[serie])
    return out


def stabilite(vals, serie):
    n = len(vals)
    if serie == "btts":
        p = sum(vals) / n
        cov = max(p, 1 - p)
    else:
        cov = sum(c for _, c in Counter(vals).most_common(2)) / n
    return "stable" if cov >= 0.8 else ("moyenne" if cov >= 0.65 else "instable")


def alertes(rows_h, rows_a, serie):
    out = []
    for nom, rows in (("dom", rows_h), ("ext", rows_a)):
        v = serie_valeurs(rows, serie)
        if stabilite(v, serie) == "instable":
            out.append(f"{nom}:instable")
        if serie != "btts":
            med = statistics.median(v)
            if any(abs(x - med) >= 2 for x in v):
                out.append(f"{nom}:pic")
            if len(v) >= 6:
                recent, avant = v[-3:], v[:-3]
                if abs(sum(recent) / 3 - sum(avant) / len(avant)) >= 1:
                    out.append(f"{nom}:rupture")
    return out


# ------------------------------------------------------------------ analyse d'un match
def orienter(rows_dom_team, rows_ext_team):
    """rows = [(buts_marques, buts_encaisses)] du plus ancien au plus récent, au même lieu.
    Retourne les scores orientés (h, a) du point de vue du match (domicile, extérieur)."""
    rh = [(gf, ga) for gf, ga in rows_dom_team]            # l'équipe jouait à domicile : h = marqués
    ra = [(ga, gf) for gf, ga in rows_ext_team]            # l'équipe jouait à l'extérieur : h = encaissés
    return rh, ra


def analyse(rows_dom_team, rows_ext_team, cotes):
    """Retourne (n_min, liste de candidats) ; None si échantillon < 4 pour l'une des deux équipes."""
    n_min = min(len(rows_dom_team), len(rows_ext_team))
    k = coef_k(n_min)
    if k is None:
        return n_min, None
    rh, ra = orienter(rows_dom_team[-FENETRE:], rows_ext_team[-FENETRE:])
    cands = []
    for key, cote in cotes.items():
        md = market_def(key)
        if md is None or not isinstance(cote, (int, float)) or cote < COTE_MIN:
            continue
        pred, serie = md
        s_h = sum(pred(h, a) for h, a in rh) / len(rh)
        s_a = sum(pred(h, a) for h, a in ra) / len(ra)
        seuil = seuil_pari(n_min, cote)
        cands.append({
            "marche": key, "cote": cote, "sH": s_h, "sA": s_a, "k": k, "seuil": seuil, "serie": serie,
            "final_moy": (s_h + s_a) / 2 * k, "final_min": min(s_h, s_a) * k,
            "alertes": alertes(rh, ra, serie), "pred": pred,
        })
    return n_min, cands


def choisir(cands, variante):
    """Un seul pari par match. Retourne (statut, candidat) ou (None, None)."""
    f = "final_" + variante
    ok = [c for c in cands if c[f] >= c["seuil"] - EPS]
    if ok:
        best = max(ok, key=lambda c: (round(c[f], 9), c["cote"]))
        return ("ALERTE" if best["alertes"] else "RETENU"), best
    near = [c for c in cands if c[f] >= c["seuil"] - MARGE_SURVEILLER - EPS]
    if near:
        best = max(near, key=lambda c: (round(c[f], 9), c["cote"]))
        return "SURVEILLER", best
    return None, None


# ------------------------------------------------------------------ données
def lignes(equipe, domicile, date_match):
    """Historique au même lieu, strictement AVANT la date du match (aucune fuite du futur)."""
    ms = [m for m in (equipe.get("matchs") or [])
          if m.get("domicile") is domicile and isinstance(m.get("buts_marques"), int)
          and isinstance(m.get("buts_encaisses"), int) and str(m.get("date") or "") < date_match]
    ms.sort(key=lambda m: str(m.get("date")))
    return [(m["buts_marques"], m["buts_encaisses"]) for m in ms]


def charger(dossier):
    vus = {}
    for f in sorted(glob.glob(dossier + "/*.json.gz")):
        for k, e in json.load(gzip.open(f)).items():
            mid = e.get("match_id", k)
            vus[mid] = e  # le fichier le plus récent remplace
    return vus


def score_reel(e):
    s = e.get("score")
    if isinstance(s, dict) and isinstance(s.get("buts_dom"), int) and isinstance(s.get("buts_ext"), int):
        return s["buts_dom"], s["buts_ext"]
    return None


# ------------------------------------------------------------------ référence V2.6.10 / V2.6.9 (picks publiés)
def base_pred(marche_moteur):
    m = marche_moteur
    t = {"victoire": lambda h, a: h > a, "defaite": lambda h, a: h < a, "nul": lambda h, a: h == a,
         "btts_oui": lambda h, a: h > 0 and a > 0, "btts_non": lambda h, a: not (h > 0 and a > 0),
         "dc_1X": lambda h, a: h >= a, "dc_X2": lambda h, a: h <= a, "dc_12": lambda h, a: h != a,
         "clean_sheet_dom": lambda h, a: a == 0, "clean_sheet_ext": lambda h, a: h == 0}
    if m in t:
        return t[m]
    r = re.fullmatch(r"(over|under)_(\d)_(\d)", m)
    if r:
        x = float(f"{r.group(2)}.{r.group(3)}")
        return (lambda h, a: h + a > x) if r.group(1) == "over" else (lambda h, a: h + a < x)
    r = re.fullmatch(r"buts_(dom|ext)_(over|under)_(\d)_(\d)", m)
    if r:
        x = float(f"{r.group(3)}.{r.group(4)}")
        over = r.group(2) == "over"
        if r.group(1) == "dom":
            return (lambda h, a: h > x) if over else (lambda h, a: h < x)
        return (lambda h, a: a > x) if over else (lambda h, a: a < x)
    r = re.fullmatch(r"handicap_(dom|ext)_([+-])(\d)_(\d)", m)
    if r:
        x = float(f"{r.group(3)}.{r.group(4)}") * (1 if r.group(2) == "+" else -1)
        if r.group(1) == "dom":
            return lambda h, a: h + x > a
        return lambda h, a: a + x > h
    return None


# ------------------------------------------------------------------ statistiques
def wilson(w, n, z=1.96):
    if n == 0:
        return (0, 0)
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0, c - r), min(1, c + r))


def resume(paris):
    n = len(paris)
    if not n:
        return {"n": 0}
    w = sum(1 for p in paris if p["gagne"])
    roi = sum((p["cote"] - 1) if p["gagne"] else -1 for p in paris) / n
    lo, hi = wilson(w, n)
    return {"n": n, "gagnes": w, "reussite": w / n, "ic95": (lo, hi), "roi": roi,
            "cote_moy": sum(p["cote"] for p in paris) / n}


def fmt(r):
    if not r.get("n"):
        return "0 pari"
    return (f"{r['n']} paris, {r['gagnes']} gagnés = {r['reussite']:.1%} "
            f"(IC95 {r['ic95'][0]:.0%}-{r['ic95'][1]:.0%}), cote moy. {r['cote_moy']:.2f}, ROI {r['roi']:+.1%}")


def rejouer(dossier):
    vus = charger(dossier)
    res = {"moy": [], "min": []}
    ref = []
    tot = Counter()
    for mid, e in vus.items():
        sc = score_reel(e)
        if sc is None:
            tot["sans_score"] += 1
            continue
        cotes = e.get("cotes_observees") or {}
        if not cotes:
            tot["sans_cotes"] += 1
            continue
        d = e["date"]
        rd = lignes(e["equipe_dom"], True, d)
        rx = lignes(e["equipe_ext"], False, d)
        n_min, cands = analyse(rd, rx, cotes)
        if cands is None:
            tot["moins_de_4"] += 1
            continue
        tot["eligibles"] += 1
        h, a = sc
        for var in ("moy", "min"):
            st, c = choisir(cands, var)
            if st:
                res[var].append({"match": mid, "statut": st, "marche": c["marche"], "cote": c["cote"],
                                 "final": c["final_" + var], "k": c["k"], "n_min": n_min, "alertes": c["alertes"],
                                 "gagne": bool(c["pred"](h, a)), "famille": famille(c["marche"]), "date": d})
        mp = (e.get("moteur_en_production") or {})
        for p, x in (mp.get("choix") or {}).items():
            pr = base_pred(x.get("marche_moteur"))
            if pr is not None and isinstance(x.get("cote"), (int, float)):
                ref.append({"match": mid, "marche": x["marche_moteur"], "cote": x["cote"], "gagne": bool(pr(h, a)),
                            "rang": p, "moteur": mp.get("version")})
    return tot, res, ref


def rapport(tot, res, ref):
    L = []
    L.append(f"Matchs éligibles (score + cotes + >= 4 matchs au même lieu, historique avant la date) : {tot['eligibles']}")
    L.append(f"Exclus : sans score {tot['sans_score']}, sans cotes {tot['sans_cotes']}, moins de 4 matchs {tot['moins_de_4']}")
    for var, titre in (("moy", "VARIANTE A (moyenne des deux côtés)"), ("min", "VARIANTE B (chaque côté passe seul)")):
        P = res[var]
        L.append("")
        L.append("=== " + titre + " ===")
        ret = [p for p in P if p["statut"] in ("RETENU", "ALERTE")]
        L.append("Retenus + alertes : " + fmt(resume(ret)))
        for st in ("RETENU", "ALERTE", "SURVEILLER"):
            L.append(f"  {st:<11}: " + fmt(resume([p for p in P if p["statut"] == st])))
        L.append("  Par taille d'échantillon (retenus+alertes) :")
        L.append("    4-5 matchs : " + fmt(resume([p for p in ret if p["n_min"] <= 5])))
        L.append("    6+ matchs  : " + fmt(resume([p for p in ret if p["n_min"] >= 6])))
        L.append("  Par zone de cote (retenus+alertes) :")
        L.append("    1,26-1,37 : " + fmt(resume([p for p in ret if p["cote"] <= COTE_BORNE])))
        L.append("    > 1,37    : " + fmt(resume([p for p in ret if p["cote"] > COTE_BORNE])))
        L.append("  Par famille de marché (retenus+alertes) :")
        for fam in sorted({p["famille"] for p in ret}):
            L.append(f"    {fam:<18}: " + fmt(resume([p for p in ret if p["famille"] == fam])))
        L.append("  Hit-rate annoncé vs réel (retenus+alertes) : annoncé moyen "
                 f"{(sum(p['final'] for p in ret) / len(ret)):.1%}" if ret else "  (aucun pari)")
    L.append("")
    L.append("=== RÉFÉRENCE : picks publiés par V2.6.10/V2.6.9 sur les mêmes matchs ===")
    L.append("Tous les picks : " + fmt(resume(ref)))
    L.append("Picks avec cote >= 1,26 : " + fmt(resume([p for p in ref if p["cote"] >= COTE_MIN])))
    L.append("Picks avec cote 1,26-1,74 : " + fmt(resume([p for p in ref if COTE_MIN <= p["cote"] <= 1.74])))
    L.append("P1 seulement : " + fmt(resume([p for p in ref if p["rang"] == "P1"])))
    return "\n".join(L)


# ------------------------------------------------------------------ tests de vérification
def tests():
    ok = True

    def chk(nom, cond):
        nonlocal ok
        print(("OK   " if cond else "ECHEC"), nom)
        ok = ok and cond

    # 3 qui passent
    chk("5/5 à 1,30 passe (90 % >= 77 %)", decide(1.0, 5, 1.30))
    chk("4/4 à 1,50 passe (80 % >= 75 %)", decide(1.0, 4, 1.50))
    chk("6/6 à 1,45 passe (100 % >= 72 %)", decide(1.0, 6, 1.45))
    # 3 qui échouent
    chk("3 matchs : exclu", coef_k(3) is None and not decide(1.0, 3, 1.50))
    chk("4/5 à 1,50 échoue (72 % < 75 %)", not decide(0.8, 5, 1.50))
    chk("4/6 à 1,30 échoue (67 %)", not decide(4 / 6, 6, 1.30))
    chk("cote 1,20 : pas de pari", not decide(1.0, 6, 1.20))
    chk("6/6 à 1,30 : seuil 77 % respecté, 5/6=83 % passe", decide(5 / 6, 6, 1.30))
    chk("5/6 à 1,50, 72 % : 4,3/6 = 0,72 passe tout juste", decide(0.72, 6, 1.50))
    # prédicats de marchés : 3 vrais, 3 faux
    pr = lambda k: market_def(k)[0]
    chk("BTTS oui (2,1) vrai", pr("BTTS - oui")(2, 1))
    chk("BTTS oui (1,0) faux", not pr("BTTS - oui")(1, 0))
    chk("Plus de 2.5 (2,1) vrai", pr("Plus de 2.5 buts")(2, 1))
    chk("Moins de 2.5 (2,1) faux", not pr("Moins de 2.5 buts")(2, 1))
    chk("Handicap 0.5 Domicile (0,0) vrai", pr("Handicap 0.5 - Domicile")(0, 0))
    chk("Handicap -1.5 Domicile (2,1) faux", not pr("Handicap -1.5 - Domicile")(2, 1))
    chk("Handicap -1.5 Extérieur (2,1) vrai", pr("Handicap -1.5 - Extérieur")(2, 1))
    chk("Double chance X2 (1,1) vrai", pr("Double chance - X2")(1, 1))
    chk("Cage inviolée Domicile (1,0) vrai", pr("Cage inviolée - Domicile")(1, 0))
    chk("Total pair ignoré", market_def("Total buts - pair") is None)
    chk("Handicap -2.5 exclu", market_def("Handicap -2.5 - Domicile") is None)
    # cas réels de la conversation
    helmond = [(1, 1), (1, 1), (4, 2), (3, 1), (2, 2)]
    nac = [(2, 1), (2, 2), (2, 4), (2, 1), (2, 2)]  # (marqués, encaissés) de NAC à l'extérieur
    n, c = analyse(helmond, nac, {"Plus de 1.5 buts": 1.30, "Plus de 3.5 buts": 1.60, "BTTS - oui": 1.60})
    d = {x["marche"]: x for x in c}
    chk("Helmond-NAC : +1,5 final 90 %", abs(d["Plus de 1.5 buts"]["final_moy"] - 0.9) < 1e-9)
    chk("Helmond-NAC : +3,5 final 54 %", abs(d["Plus de 3.5 buts"]["final_moy"] - 0.54) < 1e-9)
    st, best = choisir(c, "moy")
    chk("Helmond-NAC : pari retenu = BTTS ou +1,5 à 90 %", st in ("RETENU", "ALERTE") and abs(best["final_moy"] - 0.9) < 1e-9)
    rad = [(1, 1), (2, 1), (1, 0), (3, 1), (0, 0), (4, 4)]
    rad2 = [(1, 2), (1, 0), (0, 0), (0, 1), (0, 1), (0, 3)]
    n, c = analyse(rad, rad2, {"Double chance - 1X": 1.40, "1X2 - 1": 1.90})
    d = {x["marche"]: x for x in c}
    chk("Rad-Radnicki : 1X final 92 %", abs(d["Double chance - 1X"]["final_moy"] - 11 / 12) < 1e-9)
    chk("Rad-Radnicki : victoire Rad 58 %", abs(d["1X2 - 1"]["final_moy"] - 7 / 12) < 1e-9)
    n, c = analyse([(0, 0), (1, 2), (1, 1)], [(0, 1), (0, 0), (0, 0), (1, 1)], {"Double chance - X2": 1.40})
    chk("Grenoble-Boulogne : 3 matchs, exclu", c is None)
    # fuite du futur : un match daté le jour même ou après est ignoré
    eq = {"matchs": [{"domicile": True, "buts_marques": 1, "buts_encaisses": 0, "date": "2026-10-01"},
                     {"domicile": True, "buts_marques": 9, "buts_encaisses": 9, "date": "2026-10-10"},
                     {"domicile": True, "buts_marques": 9, "buts_encaisses": 9, "date": "2026-10-11"}]}
    chk("Aucune fuite : seuls les matchs strictement avant la date", lignes(eq, True, "2026-10-10") == [(1, 0)])
    print("TOUS LES TESTS OK" if ok else "DES TESTS ECHOUENT")
    return ok


if __name__ == "__main__":
    if sys.argv[1] == "--test":
        sys.exit(0 if tests() else 1)
    tot, res, ref = rejouer(sys.argv[1])
    txt = rapport(tot, res, ref)
    print(txt)
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8") as fh:
            json.dump({"retenus_moy": res["moy"], "retenus_min": res["min"], "ref": ref}, fh, ensure_ascii=False)
