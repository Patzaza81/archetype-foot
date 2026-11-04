import numpy as np
import pouvoir_predictif_v3 as v3

def _m(n=150, seed=0):
    r = np.random.default_rng(seed); eq = list("ABCDEFGH"); M = []
    for i in range(n):
        h, a = r.choice(eq, 2, replace=False); M.append((730000 + i // 4, 0, str(h), str(a), int(r.poisson(1.5)), int(r.poisson(1.1))))
    return sorted(M, key=lambda m: (m[0], m[1]))

def test_variables_futur_sans_effet():
    M = _m(); mu = np.full((len(M), 2), 1.3); X = v3.variables(M, 0.05, mu); M2 = list(M)
    for i in range(100, 150): M2[i] = M2[i][:4] + (9, 0)
    assert np.allclose(X[:100], v3.variables(M2, 0.05, mu)[:100], equal_nan=True)

def test_variables_meme_jour_sans_effet():
    M = _m(); mu = np.full((len(M), 2), 1.3); i = 70; j = i
    while M[j][0] == M[i][0]: j += 1
    M2 = list(M); M2[i] = M2[i][:4] + (8, 0)
    assert np.allclose(v3.variables(M, 0.05, mu)[i:j], v3.variables(M2, 0.05, mu)[i:j], equal_nan=True)

def test_h2h_orientation():
    M = [(1, 0, "A", "B", 3, 0), (10, 0, "B", "A", 0, 0), (20, 0, "A", "B", 1, 1), (30, 0, "B", "A", 1, 1)]
    X = v3.variables(M, 0.05, np.full((4, 2), 1.3))
    # avant le match 4 (B dom): A a gagne puis 2 nuls -> part de victoire de B < 0.5 (lissage vers 0.5)
    assert X[3, 15] < 0.5 and X[1, 15] < 0.5   # B dom contre A, A a gagne la 1re confrontation

def test_pas_de_melange_de_competitions():
    import inspect; src = inspect.getsource(v3.analyser)
    assert "pool" not in src.lower() and "POOL" not in src
