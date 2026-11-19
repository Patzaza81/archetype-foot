"""E11a : table élargie (bloc). Ajoute aux 57 variables de E7 : formes de résultats (victoire/nul/défaite, dépassements 1,5/2,5/3,5, BTTS, cages inviolées, séries, 3 et 5 derniers),
face-à-face des deux équipes (rencontres antérieures du bloc), repos et densité des matchs, avantage du terrain propre à chaque équipe, et — sur les matchs où elles existent — mi-temps, tirs, tirs cadrés, corners, cartons.
Tout est antérieur au jour du match. Aucune cote."""
import time, collections, numpy as np
import commun as C
from commun import *
import e7_table as E7
C.MEQ = 32.0
mb, sb, _ = C.charger_bloc(); C.MEQ = 32.0
lig = {k: M.Ligue(v) for k, v in M.index_ligues(mb).items()}
cols = [C.IDX[k] for k in C.CLES]
def ordn(s): return np.datetime64(s, "D").astype(int)
def forme(recs):
    g = np.array([r["gf"] for r in recs], float); a = np.array([r["ga"] for r in recs], float); t = g + a
    return {"w": (g > a).mean(), "dr": (g == a).mean(), "l": (g < a).mean(), "o15": (t > 1.5).mean(), "o25": (t > 2.5).mean(), "o35": (t > 3.5).mean(),
            "btts": ((g > 0) & (a > 0)).mean(), "cs": (a == 0).mean(), "w2": ((g - a) >= 2).mean(), "l2": ((a - g) >= 2).mean(), "gd": (g - a).mean()}
def stat(recs, k):
    v = [r[k] for r in recs if r.get(k) is not None]
    return (np.mean(v), len(v)) if v else (np.nan, 0)
h2h = collections.defaultdict(list)       # (équipe_dom, équipe_ext) non ordonné -> [(domicile, exterieur, h, a)]
rows, P, Y, meta = [], [], [], []; t0 = time.time()
par_jour = collections.defaultdict(list)
for m in mb: par_jour[m["jour"]].append(m)
for jour in sorted(par_jour):
    for m in par_jour[jour]:
        F = C.features(m, lig)
        if F is None: continue
        f = E7.vecteur(m, F)
        A, Aa, B, Bh = [r for r in m["md"] if r["dom"]], [r for r in m["md"] if not r["dom"]], [r for r in m["me"] if not r["dom"]], [r for r in m["me"] if r["dom"]]
        fa, fb = forme(A), forme(B)
        for k in fa: f["A_" + k] = fa[k]; f["B_" + k] = fb[k]
        f["A5_ppm"] = np.mean([3 * (r["gf"] > r["ga"]) + (r["gf"] == r["ga"]) for r in m["md"][-5:]]); f["B5_ppm"] = np.mean([3 * (r["gf"] > r["ga"]) + (r["gf"] == r["ga"]) for r in m["me"][-5:]])
        f["A3_gd"] = np.mean([r["gf"] - r["ga"] for r in m["md"][-3:]]); f["B3_gd"] = np.mean([r["gf"] - r["ga"] for r in m["me"][-3:]])
        f["A5_tot"] = np.mean([r["gf"] + r["ga"] for r in m["md"][-5:]]); f["B5_tot"] = np.mean([r["gf"] + r["ga"] for r in m["me"][-5:]])
        f["A_homeadv"] = fa["gd"] - (np.mean([r["gf"] - r["ga"] for r in Aa]) if Aa else 0.0); f["B_homeadv"] = (np.mean([r["gf"] - r["ga"] for r in Bh]) if Bh else 0.0) - fb["gd"]
        d0 = ordn(jour); f["A_rest"] = min(60, d0 - ordn(m["md"][-1]["date"])); f["B_rest"] = min(60, d0 - ordn(m["me"][-1]["date"]))
        f["A_dens"] = sum(d0 - ordn(r["date"]) <= 14 for r in m["md"]); f["B_dens"] = sum(d0 - ordn(r["date"]) <= 14 for r in m["me"])
        f["A_n"] = len(m["md"]); f["B_n"] = len(m["me"])
        key = frozenset((m["domicile"], m["exterieur"])); H = h2h.get(key, [])
        f["h2h_n"] = len(H)
        if H:
            f["h2h_tot"] = np.mean([h + a for _, _, h, a in H]); f["h2h_btts"] = np.mean([h > 0 and a > 0 for _, _, h, a in H])
            f["h2h_win_A"] = np.mean([(h > a) if dm == m["domicile"] else (a > h) for dm, _, h, a in H]); f["h2h_draw"] = np.mean([h == a for _, _, h, a in H])
            f["h2h_gd_A"] = np.mean([(h - a) if dm == m["domicile"] else (a - h) for dm, _, h, a in H])
        else:
            for k in ("h2h_tot", "h2h_btts", "h2h_win_A", "h2h_draw", "h2h_gd_A"): f[k] = np.nan
        for k in ("ht_f", "ht_a", "sh_f", "sh_a", "sot_f", "sot_a", "co_f", "co_a", "yc_f"):
            f["A_" + k], _ = stat(A, k); f["B_" + k], _ = stat(B, k)
        h, a = sb[m["id"]]; la, lb = C.lambdas(F, None, 0.328, "gd")
        P.append(C.probas(np.array([la]), np.array([lb]))[0][cols]); Y.append(C.TAB[min(h, 10), min(a, 10)][cols]); rows.append(f); meta.append((m["id"], jour, m["competition"], h, a))
    for m in par_jour[jour]:
        h2h[frozenset((m["domicile"], m["exterieur"]))].append((m["domicile"], m["exterieur"], *sb[m["id"]]))
names = list(rows[0]); X = np.array([[r.get(k, np.nan) for k in names] for r in rows], float)
np.savez_compressed("sorties/table2_bloc.npz", X=X, names=np.array(names), P=np.array(P), Y=np.array(Y), id=np.array([x[0] for x in meta]), jour=np.array([x[1] for x in meta]), comp=np.array([x[2] for x in meta]))
print(len(X), "matchs", len(names), "variables", round(time.time() - t0), "s ; part NaN par groupe : h2h", np.isnan(X[:, names.index("h2h_tot")]).mean().round(3), "tirs", np.isnan(X[:, names.index("A_sh_f")]).mean().round(3), "mi-temps", np.isnan(X[:, names.index("A_ht_f")]).mean().round(3))
