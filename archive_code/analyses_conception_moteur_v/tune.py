import pickle, numpy as np, itertools, math
from scipy.optimize import minimize
rows = pickle.load(open("rows.pkl", "rb"))
def lg(p): p = np.clip(p, 0.02, 0.98); return np.log(p / (1 - p))
def feats(R):
    f = np.array([r["final"] for r in R]); imp = np.array([1 / r["cote"] for r in R])
    return np.column_stack([np.ones(len(R)), lg(f), lg(imp)])
def fit(R, use_freq=True, l2=1.0):
    X = feats(R); y = np.array([r["gagne"] for r in R], float)
    if not use_freq: X = X[:, [0, 2]]
    def nll(w):
        z = X @ w; return np.sum(np.logaddexp(0, z) - y * z) + l2 * np.sum(w[1:] ** 2) * 0.5
    w0 = np.zeros(X.shape[1]); w = minimize(nll, w0, method="BFGS").x
    return w
def predict(R, w, use_freq=True):
    X = feats(R)
    if not use_freq: X = X[:, [0, 2]]
    return 1 / (1 + np.exp(-(X @ w)))
def play(R, P, e, cmin, cmax):
    by = {}
    for r, p in zip(R, P):
        if not (cmin <= r["cote"] <= cmax): continue
        ev = p * r["cote"] - 1
        if r["match"] not in by or ev > by[r["match"]][0]: by[r["match"]] = (ev, r)
    bets = [r for ev, r in by.values() if ev >= e]
    n = len(bets)
    if n == 0: return 0, 0, 0
    w = sum(r["gagne"] for r in bets); roi = sum((r["cote"] - 1) if r["gagne"] else -1 for r in bets) / n
    return n, w / n, roi
def split(date_max):
    tr = [r for r in rows if r["date"] <= date_max]; te = [r for r in rows if r["date"] > date_max]
    return tr, te
if __name__ == "__main__":
    print("== Information de la fréquence au-delà de la cote ==")
    w1 = fit(rows, True); w0 = fit(rows, False)
    print("avec fréquence : a=%.2f  b(freq)=%.2f  c(cote)=%.2f" % tuple(w1))
    ll = lambda w, uf: -np.sum(np.array([r['gagne'] for r in rows]) * np.log(predict(rows, w, uf)) + (1 - np.array([r['gagne'] for r in rows])) * np.log(1 - predict(rows, w, uf)))
    print("log-vraisemblance : cote seule %.1f ; cote+fréquence %.1f ; gain %.1f" % (ll(w0, False), ll(w1, True), ll(w0, False) - ll(w1, True)))
    grid = list(itertools.product([0, 0.02, 0.04, 0.06, 0.08, 0.10], [1.5, 1.74, 2.2, 3.0]))
    for dm in ("2026-10-09", "2026-10-10"):
        tr, te = split(dm)
        w = fit(tr, True); Ptr = predict(tr, w); Pte = predict(te, w)
        print(f"\n== Réglage sur matchs <= {dm} : {len({r['match'] for r in tr})} matchs ; test sur {len({r['match'] for r in te})} ==")
        print("coeffs a=%.2f b=%.2f c=%.2f" % tuple(w))
        res = []
        for e, cmax in grid:
            n, hit, roi = play(tr, Ptr, e, 1.26, cmax)
            if n >= 30: res.append((roi, e, cmax, n, hit))
        res.sort(reverse=True)
        for roi, e, cmax, n, hit in res[:5]:
            nt, ht, rt = play(te, Pte, e, 1.26, cmax)
            print(f"  e={e:.2f} cmax={cmax}: réglage {n} paris {hit:.1%} ROI {roi:+.1%} | test {nt} paris {ht:.1%} ROI {rt:+.1%}")
