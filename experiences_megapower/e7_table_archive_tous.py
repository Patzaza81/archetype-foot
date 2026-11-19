"""E7a : table de variables « croisements de buts » (18-19/11/2026). Buts seulement, aucune cote. Tout est calculé AVANT le match (historique strictement antérieur).
Construit data cache : sorties/table_bloc.npz et sorties/table_archive.npz (matchs, variables, probabilités du modèle de base, issues)."""
import sys, time, numpy as np
import commun as C
from commun import *
K = 4.0   # rapprochement vers la moyenne du championnat pour les venues rares (équipe à l'extérieur / à domicile hors rôle du match)

def prof(recs, mu_f, mu_a, last=None):
    if last: recs = recs[-last:]
    n = len(recs)
    gf = np.array([r["gf"] for r in recs], float); ga = np.array([r["ga"] for r in recs], float)
    return gf, ga, n

def shr(x_sum, mu, n):       # moyenne normalisée par la moyenne du championnat, rapprochée de 1
    return (x_sum / mu + K) / (n + K)

def vecteur(m, F):
    A = [r for r in m["md"] if r["dom"]]; Aa = [r for r in m["md"] if not r["dom"]]
    B = [r for r in m["me"] if not r["dom"]]; Bh = [r for r in m["me"] if r["dom"]]
    mh, me = F["mu_h"], F["mu_e"]; mt = (mh + me) / 2
    f = {}
    gA, aA, nA = prof(A, mh, me); gB, aB, nB = prof(B, me, mh)
    f["hgf"] = gA.mean() / mh; f["hga"] = aA.mean() / me; f["bgf_a"] = gB.mean() / me; f["bga_a"] = aB.mean() / mh      # domicile de A, extérieur de B
    gAa, aAa, nAa = prof(Aa, me, mh); gBh, aBh, nBh = prof(Bh, mh, me)
    f["agf_A"] = shr(gAa.sum(), me, nAa); f["aga_A"] = shr(aAa.sum(), mh, nAa)                                           # A à l'extérieur
    f["bgf_h"] = shr(gBh.sum(), mh, nBh); f["bga_h"] = shr(aBh.sum(), me, nBh)                                           # B à domicile
    f["Agf_all"] = (gA.sum() + gAa.sum()) / (nA + nAa) / mt; f["Aga_all"] = (aA.sum() + aAa.sum()) / (nA + nAa) / mt
    f["Bgf_all"] = (gB.sum() + gBh.sum()) / (nB + nBh) / mt; f["Bga_all"] = (aB.sum() + aBh.sum()) / (nB + nBh) / mt
    f["tot_h"] = (gA + aA).mean() / (mh + me); f["tot_a"] = (gB + aB).mean() / (mh + me)
    g5, a5, n5 = prof(A, mh, me, 5); h5, b5, _ = prof(B, me, mh, 5)
    f["hgf5"] = g5.mean() / mh; f["hga5"] = a5.mean() / me; f["bgf5"] = h5.mean() / me; f["bga5"] = b5.mean() / mh
    f["sd_hgf"] = gA.std(); f["sd_hga"] = aA.std(); f["sd_bgf"] = gB.std(); f["sd_bga"] = aB.std()
    f["p0f_h"] = (gA == 0).mean(); f["p0a_h"] = (aA == 0).mean(); f["p0f_a"] = (gB == 0).mean(); f["p0a_a"] = (aB == 0).mean()
    f["p3_h"] = ((gA + aA) >= 3).mean(); f["p3_a"] = ((gB + aB) >= 3).mean()
    f["ppm_h"] = (3 * (gA > aA) + (gA == aA)).mean(); f["ppm_a"] = (3 * (gB > aB) + (gB == aB)).mean()
    # croisements
    f["x1"] = f["hgf"] * f["bga_a"]; f["x2"] = f["bgf_a"] * f["hga"]          # attaque dom de A x défense ext de B ; attaque ext de B x défense dom de A
    f["x3"] = f["agf_A"] * f["bga_h"]; f["x4"] = f["bgf_h"] * f["aga_A"]      # inverses : A à l'extérieur contre B à domicile
    f["xa1"] = f["Agf_all"] * f["Bga_all"]; f["xa2"] = f["Bgf_all"] * f["Aga_all"]
    for n_, (a, b) in {"d12": ("x1", "x2"), "d34": ("x3", "x4"), "da": ("xa1", "xa2")}.items():
        f[n_] = f[a] - f[b]; f["l" + n_] = np.log((f[a] + 1e-3) / (f[b] + 1e-3)); f["s" + n_] = f[a] + f[b]
    f["r_att"] = f["hgf"] / (f["bgf_a"] + 1e-3); f["r_def"] = f["hga"] / (f["bga_a"] + 1e-3)
    f["gaver_h"] = (gA - aA).mean(); f["gaver_a"] = (gB - aB).mean(); f["gap_ga"] = f["gaver_h"] - f["gaver_a"]
    f["gd_all"] = ((gA.sum() + gAa.sum() - aA.sum() - aAa.sum()) / (nA + nAa)) - ((gB.sum() + gBh.sum() - aB.sum() - aBh.sum()) / (nB + nBh))
    f["ppm_gap"] = F["ecarts"]["ppm"]; f["gd_gap"] = F["ecarts"]["gd"]
    f["lig_tot"] = mh + me; f["lig_hadv"] = mh / me
    f["n_h"] = nA; f["n_a"] = nB
    return f

def construire(matchs, sc, lig, nom):
    t0 = time.time(); rows, P, Y, meta = [], [], [], []
    for m in matchs:
        F = C.features(m, lig)
        if F is None or m["id"] not in sc: continue
        la, lb = C.lambdas(F, None, 0.328, "gd")
        P.append(C.probas(np.array([la]), np.array([lb]))[0]); rows.append(vecteur(m, F))
        h, a = sc[m["id"]]; Y.append(C.TAB[min(h, 10), min(a, 10)]); meta.append((m["id"], m["jour"], m["competition"], h, a))
    names = list(rows[0]); X = np.array([[r[k] for k in names] for r in rows], float)
    cols = list(range(len(C.NOMS)))
    np.savez_compressed(f"sorties/table_{nom}_tous.npz", X=X, names=np.array(names), P=np.array(P)[:, cols], Y=np.array(Y)[:, cols], id=np.array([x[0] for x in meta]),
                        jour=np.array([x[1] for x in meta]), comp=np.array([x[2] for x in meta]), h=np.array([x[3] for x in meta]), a=np.array([x[4] for x in meta]))
    print(nom, len(X), "matchs", X.shape[1], "variables", round(time.time() - t0), "s", flush=True)

if __name__ == "__main__":
    C.MEQ = 32.0
    ma, sa, la_ = C.charger(); C.MEQ = 32.0
    la_ = {k: M.Ligue(v) for k, v in M.index_ligues(ma).items()}
    construire(ma, sa, la_, "archive")
