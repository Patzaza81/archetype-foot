import sys, json, gzip, glob, os
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, R); os.chdir(R)
import verif_pronostic as V, p1_page_donnees as pd
S = pd.scores(V.FLUX)
X = {}
for f in sorted(glob.glob(os.path.join(V.FLUX, "*.json.gz"))):
    for x in json.load(gzip.open(f)).values(): X[x["match_id"]] = x
cfg = {**V.config(), "sans_regles": True}
def sm(mid, mk):
    x = X.get(mid)
    if not x: return None
    r = V.constat(x, mk, None, cfg)
    if "A" not in r or None in (r["A"]["buts_marques"], r["B"]["buts_marques"]): return None
    return r["A"]["buts_marques"] + r["B"]["buts_marques"]
def rapport(nom, lignes):
    g = {}
    for mid, mk, date in lignes:
        sc = S.get(mid); s = sm(mid, mk)
        if sc is None or s is None: continue
        ok = bool(V.TABLE[min(sc["buts_dom"], V.CAP), min(sc["buts_ext"], V.CAP), V.IDX[mk]])
        fam = "seul" if mk == "total_moins_3.5" else "combo"
        for k in (("tous", fam), ("<=3.1", fam) if s <= 3.1 else (">3.1", fam)):
            d = g.setdefault(k, [0, 0, set(), set()]); d[0] += 1; d[1] += ok; d[2].add(mid); d[3].add(date)
    print("==", nom)
    for k in sorted(g):
        n, r, m, j = g[k]; print(f"  {k[1]:6} {k[0]:6} paris {n:4} matchs {len(m):4} réussis {r:4} taux {r/n:.1%}  {min(j)} -> {max(j)}")
J = V.lire_journal()
rapport("journal Analyse Verdict (verdicts TIENT / TIENT AVEC RÉSERVE)", [(r["match_id"], r["marche"], r["date"]) for r in J if "moins_3.5" in r["marche"] and r["verdict"] in ("TIENT", "TIENT AVEC RÉSERVE")])
etat = {}
for r in V.lire_journal(V.JOURNAL_SELECTIONS): etat[(r["match_id"], r["selection"])] = r
par = {}
for (mid, sel), r in etat.items():
    for p in r["paris"]:
        if "moins_3.5" in p["marche"]: par.setdefault(sel, []).append((mid, p["marche"], r["date"]))
for sel, L in par.items(): rapport(f"sélection gelée « {sel} »", L)
