import pickle, numpy as np
from collections import defaultdict
rows = pickle.load(open("rows2.pkl", "rb"))
rng = np.random.default_rng(7)
def stats(R, B=600):
    if not R: return None
    by = defaultdict(list)
    for r in R: by[r["match"]].append(r)
    ms = list(by)
    S = np.array([[sum(x["gagne"] - 1 / x["cote"] for x in by[m]), sum(x["gagne"] - x["final"] for x in by[m]),
                   sum(x["gagne"] * x["cote"] - 1 for x in by[m]), len(by[m])] for m in ms])
    tot = S.sum(0); n = tot[3]
    est = tot[:3] / n
    bs = []
    for _ in range(B):
        idx = rng.integers(0, len(ms), len(ms)); t = S[idx].sum(0); bs.append(t[:3] / t[3])
    bs = np.array(bs); lo = np.percentile(bs, 2.5, 0); hi = np.percentile(bs, 97.5, 0)
    return {"n": int(n), "m": len(ms), "reel": float(np.mean([r["gagne"] for r in R])), "annonce": float(np.mean([r["final"] for r in R])),
            "impl": float(np.mean([1 / r["cote"] for r in R])), "edge": est[0], "edge_ci": (lo[0], hi[0]),
            "gap": est[1], "gap_ci": (lo[1], hi[1]), "roi": est[2], "roi_ci": (lo[2], hi[2])}
def show(titre, groupes, minm=25):
    print("\n##", titre)
    print(f"{'cellule':<26}{'lignes':>7}{'matchs':>7}{'annoncé':>9}{'réel':>7}{'cote→':>7}{'écart annoncé':>15}{'avantage/cote':>20}{'ROI':>8}")
    for nom, R in groupes:
        s = stats(R)
        if not s or s["m"] < minm: continue
        f1 = "*" if (s["gap_ci"][1] < 0 or s["gap_ci"][0] > 0) else " "
        f2 = "*" if (s["edge_ci"][1] < 0 or s["edge_ci"][0] > 0) else " "
        print(f"{nom:<26}{s['n']:>7}{s['m']:>7}{s['annonce']:>9.1%}{s['reel']:>7.1%}{s['impl']:>7.1%}"
              f"{s['gap']:>+9.1%}[{s['gap_ci'][0]:+.0%},{s['gap_ci'][1]:+.0%}]{f1}"
              f"{s['edge']:>+8.1%}[{s['edge_ci'][0]:+.0%},{s['edge_ci'][1]:+.0%}]{f2}{s['roi']:>+8.1%}")
if __name__ == "__main__":
    bins = [(0, .3), (.3, .5), (.5, .6), (.6, .7), (.7, .8), (.8, .9), (.9, 1.01)]
    show("1. CALIBRATION : pourcentage final annoncé (toutes les lignes match×marché)", [(f"final {a:.0%}-{min(b,1):.0%}", [r for r in rows if a <= r["final"] < b]) for a, b in bins])
    cb = [(1.26, 1.37), (1.37, 1.5), (1.5, 1.7), (1.7, 2.0), (2.0, 3.0), (3.0, 99)]
    show("2. PAR COTE (lignes avec final >= 60 %)", [(f"cote {a}-{b}", [r for r in rows if a <= r["cote"] < b and r["final"] >= .6]) for a, b in cb])
    show("3. PAR COTE (lignes avec final >= 80 %)", [(f"cote {a}-{b}", [r for r in rows if a <= r["cote"] < b and r["final"] >= .8]) for a, b in cb])
    hi = [r for r in rows if r["final"] >= .6]
    show("4. PAR TAILLE D'ÉCHANTILLON le plus court (final >= 60 %)", [(f"n_min {a}-{b}", [r for r in hi if a <= r["n_min"] <= b]) for a, b in [(4, 4), (5, 5), (6, 7), (8, 11), (12, 12)]])
    show("5. ACCORD DES DEUX CÔTÉS |sH-sA| (final >= 60 %)", [(f"écart {a}-{b}", [r for r in hi if a <= r["ecart"] < b]) for a, b in [(0, .1), (.1, .2), (.2, .35), (.35, 1.01)]])
    show("6. FAMILLE × DIRECTION (final >= 60 %)", [(f"{f}/{d}/{c}", [r for r in hi if r["fam"] == f and r["dir"] == d and r["cible"] == c])
        for f, d, c in sorted({(r["fam"], r["dir"], r["cible"]) for r in hi})])
    comps = defaultdict(list)
    for r in hi: comps[r["comp"]].append(r)
    show("7. PAR CHAMPIONNAT (final >= 60 %, >= 25 matchs)", [(k[:24], v) for k, v in sorted(comps.items(), key=lambda kv: -len(kv[1])) if len({x['match'] for x in v}) >= 25])
