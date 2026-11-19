"""E17 : sur les SEULS pronostics éligibles (cote Betpawa >= 1,26 — filtre opérationnel, jamais variable du modèle), que partagent les pronostics gagnants, et qu'est-ce qui améliore la sélection ?
Archive (28/09 → 21/11/2026), découpage chronologique A (50 %) / B (25 %) / C (25 %, jamais utilisé). Variables = résultats connus avant le match (57 variables de buts).
1) Profil : pour chaque variable, AUC gagnants contre perdants sur A, B et C ; retenue si même sens partout et |AUC-0,5| >= 0,03 sur A.
2) Sélection : régression L1 (variables + modèle actuel) apprise sur A, réglée sur B ; on compare sur C la réussite des q % de matchs les mieux classés par le modèle actuel et par le nouveau classement."""
import sys, glob, gzip, json, warnings, numpy as np
warnings.filterwarnings("ignore")
from sklearn.linear_model import LogisticRegression as LR
from sklearn.metrics import roc_auc_score as AUC
import commun as C
from commun import *
T = np.load("sorties/table_archive_tous.npz", allow_pickle=True)
o = np.argsort(T["jour"], kind="stable"); X, P, Y, ids, jour, names = T["X"][o], T["P"][o], T["Y"][o], T["id"][o], T["jour"][o], list(T["names"])
cot = {}; want = set(ids)
for f in sorted(glob.glob(str(ROOT / "data" / "archive_test" / "*.json.gz"))):
    for k, x in json.load(gzip.open(f)).items():
        if k in want: cot[k] = V.cotes_betpawa(x.get("cotes_betpawa") or {})
lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
rng = np.random.default_rng(1)
PRIO = ["1", "2", "1N", "N2", "12", "total_plus_1.5", "total_moins_3.5", "total_moins_4.5", "total_plus_2.5", "total_moins_2.5", "btts_oui", "btts_non", "dom_moins_2.5", "ext_moins_2.5", "dom_moins_1.5", "ext_moins_1.5", "cage_dom_non", "cage_ext_non", "dom_plus_0.5", "ext_plus_0.5",
        "1N&total_plus_1.5", "N2&total_plus_1.5", "1N&total_moins_3.5", "N2&total_moins_3.5", "12&total_plus_1.5", "12&total_moins_4.5", "1N&total_moins_4.5"]
print(f"archive : {len(X)} matchs analysables et joués ; {jour[0]} → {jour[-1]}")
rows = []
for nm in PRIO:
    j = C.IDX[nm]; c = np.array([cot.get(i, {}).get(nm, np.nan) for i in ids]); el = c >= 1.26
    n = int(el.sum())
    if n < 200: print(f"\n[{nm}] éligibles (cote ≥ 1,26) : {n} → trop peu, non analysé"); continue
    xe, pe, ye, je = X[el], P[el, j], Y[el, j], jour[el]; iA, iB = int(n * .5), int(n * .75); sA, sB, sC = slice(0, iA), slice(iA, iB), slice(iB, n)
    print(f"\n[{nm}] éligibles {n} (A={iA}, B={iB-iA}, C={n-iB}) ; réussite des éligibles : A {ye[sA].mean():.3f} B {ye[sB].mean():.3f} C {ye[sC].mean():.3f} ; cote médiane {np.median(c[el]):.2f}")
    # 1) profil des gagnants
    com = []
    for v, vn in enumerate(names):
        a = [AUC(ye[s], xe[s, v]) if 0 < ye[s].sum() < len(ye[s]) and np.std(xe[s, v]) > 0 else 0.5 for s in (sA, sB, sC)]
        if abs(a[0] - .5) >= 0.03 and all((x - .5) * (a[0] - .5) > 0 for x in a[1:]): com.append((abs(a[0] - .5), vn, a))
    com.sort(reverse=True)
    for _, vn, a in com[:6]:
        v = names.index(vn); gm, pm = np.median(xe[ye == 1, v]), np.median(xe[ye == 0, v])
        print(f"   commun aux gagnants : {vn:9s} médiane gagnants {gm:+.2f} contre perdants {pm:+.2f} | AUC A/B/C {a[0]:.3f} {a[1]:.3f} {a[2]:.3f}")
    if not com: print("   aucune variable avec le même sens sur A, B et C")
    # 2) sélection
    lo, hi = np.percentile(xe[sA], 1, axis=0), np.percentile(xe[sA], 99, axis=0); Z = (np.clip(xe, lo, hi) - np.clip(xe, lo, hi)[sA].mean(0)) / (np.clip(xe, lo, hi)[sA].std(0) + 1e-9)
    F = np.c_[10 * lg(pe), Z]; best = None
    for cc in (0.003, 0.01, 0.03, 0.1, 0.3):
        m = LR(penalty="l1", solver="liblinear", C=cc, max_iter=2000).fit(F[sA], ye[sA]); l = -np.mean(ye[sB] * np.log(np.clip(m.predict_proba(F[sB])[:, 1], 1e-6, 1)) + (1 - ye[sB]) * np.log(np.clip(1 - m.predict_proba(F[sB])[:, 1], 1e-6, 1)))
        if best is None or l < best[0]: best = (l, cc)
    m = LR(penalty="l1", solver="liblinear", C=best[1], max_iter=2000).fit(F[:iB], ye[:iB]); pn = m.predict_proba(F[sC])[:, 1]; pcur = pe[sC]; yc = ye[sC]
    sel = [(names[i - 1], m.coef_[0][i]) for i in np.argsort(-np.abs(m.coef_[0][1:])) + 1 if abs(m.coef_[0][i]) > 1e-6][:5]
    a0, a1 = AUC(yc, pcur), AUC(yc, pn)
    out = f"   C : AUC modèle actuel {a0:.3f} → nouveau {a1:.3f}"
    for q in (0.2, 0.4):
        k = max(10, int(q * len(yc))); ha = yc[np.argsort(-pcur, kind="stable")[:k]].mean(); hb = yc[np.argsort(-pn, kind="stable")[:k]].mean()
        d = [yc[rng.choice(np.argsort(-pn, kind="stable")[:k], k)].mean() - yc[rng.choice(np.argsort(-pcur, kind="stable")[:k], k)].mean() for _ in range(300)]
        out += f" | top {q:.0%} (n={k}) réussite {ha:.3f} → {hb:.3f} [{100*np.percentile(d,2.5):+.1f} ; {100*np.percentile(d,97.5):+.1f}]"
        rows.append((nm, q, k, ha, hb))
    print(out + "\n   variables utiles (coef) : " + (", ".join(f"{a}:{b:+.2f}" for a, b in sel) or "aucune"))
