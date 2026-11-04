import numpy as np
import pouvoir_predictif_v2 as v2

def _matchs(n=120, seed=0):
    r = np.random.default_rng(seed); eq = list("ABCDEFGH"); M = []
    for i in range(n):
        h, a = r.choice(eq, 2, replace=False); M.append((730000 + i // 4, 0, str(h), str(a), int(r.poisson(1.5)), int(r.poisson(1.1))))
    return sorted(M, key=lambda m: (m[0], m[1]))

def test_extras_futur_sans_effet_sur_le_passe():
    M = _matchs(); X = v2.extras(M, 0.05); M2 = list(M)
    for i in range(80, 120): M2[i] = M2[i][:4] + (9, 0)
    X2 = v2.extras(M2, 0.05)
    assert np.allclose(X[:80], X2[:80], equal_nan=True)

def test_extras_meme_jour_sans_effet():
    M = _matchs(); i = 60; j = i
    while j < len(M) and M[j][0] == M[i][0]: j += 1
    M2 = list(M); M2[i] = M2[i][:4] + (8, 0); X, X2 = v2.extras(M, 0.05), v2.extras(M2, 0.05)
    assert np.allclose(X[i:j], X2[i:j], equal_nan=True)

def test_extras_tirs_cadres_futur_sans_effet():
    M = _matchs(); sot = np.random.default_rng(1).integers(0, 10, (len(M), 2)).astype(float); s2 = sot.copy(); s2[80:] = 50
    X, X2 = v2.extras(M, 0.05, sot), v2.extras(M, 0.05, s2)
    assert np.allclose(X[:80], X2[:80], equal_nan=True)

def test_ajuster_recupere_un_signal():
    r = np.random.default_rng(2); X = r.normal(size=(2000, 2)); y = (r.random(2000) < 1 / (1 + np.exp(-2 * X[:, 0]))).astype(float)
    p = v2.predire_logit(v2.ajuster(X, y, 1.0), X)
    assert v2.lb(p, y).mean() < v2.lb(np.full(2000, y.mean()), y).mean() - 0.1
