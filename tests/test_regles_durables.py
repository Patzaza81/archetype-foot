import numpy as np
import regles_durables as rd

def _M(n=150, seed=0):
    r = np.random.default_rng(seed); eq = list("ABCDEFGH"); M = []
    for i in range(n):
        h, a = r.choice(eq, 2, replace=False); M.append((730000 + i // 4, "2122" if i < 75 else "2223", str(h), str(a), int(r.poisson(1.5)), int(r.poisson(1.1))))
    return M

def _PR(seed=0, n=1500):
    r = np.random.default_rng(seed); S = np.repeat(np.arange(5), n // 5); D = 730000 + np.arange(n)
    X = r.normal(size=(n, len(rd.NOMS) - 1)); p = np.clip(0.5 + 0.1 * r.normal(size=(n, 7)), 0.05, 0.95)
    Y = (r.random((n, 7)) < p + 0.15 * (X[:, [0]] > 0.5)).astype(float)
    return dict(S=S, D=D, Y=Y, valide=np.ones(n, bool), P1=p, X=X, start={s: D[S == s].min() for s in range(5)})

def test_plus_futur_et_meme_jour_sans_effet():
    M = _M(); X = rd.plus(M); M2 = list(M)
    for i in range(100, 150): M2[i] = M2[i][:4] + (9, 0)
    assert np.allclose(X[:100], rd.plus(M2)[:100], equal_nan=True)
    i = 60; j = i
    while M[j][0] == M[i][0]: j += 1
    M3 = list(M); M3[i] = M3[i][:4] + (8, 0); assert np.allclose(X[i:j], rd.plus(M3)[i:j], equal_nan=True)

def test_journee_remise_a_zero_a_chaque_saison():
    X = rd.plus(_M()); assert X[0, rd.NOMS_PLUS.index("journee_min")] == 0 and X[75, rd.NOMS_PLUS.index("journee_min")] == 0

def test_ensembles_ne_voient_pas_la_saison_suivante():
    PR = _PR(); PR2 = {k: (v.copy() if hasattr(v, "copy") else v) for k, v in PR.items()}
    s = 3; PR2["Y"][PR["D"] >= PR["start"][s]] = 1 - PR2["Y"][PR["D"] >= PR["start"][s]]
    a, b = rd.ensembles(PR, 0), rd.ensembles(PR2, 0)
    for k in (1, 2, 3): assert [q["cond"] for q in a[k]] == [q["cond"] for q in b[k]]
    assert [q["cond"] for q in a[4]] != [q["cond"] for q in b[4]] or len(a[4]) == 0

def test_equivalence_signe_et_recouvrement():
    m1 = np.zeros(100, bool); m1[:60] = True; m2 = np.zeros(100, bool); m2[:50] = True; m3 = np.zeros(100, bool); m3[50:] = True
    q = {"r": 0.1, "mem": m1}
    assert rd.meilleur(q, [{"r": 0.2, "mem": m2}], 0.5) is not None
    assert rd.meilleur(q, [{"r": -0.2, "mem": m2}], 0.5) is None
    assert rd.meilleur(q, [{"r": 0.2, "mem": m3}], 0.5) is None

def test_texte_simplifie_les_bornes():
    j = rd.IDX["elo_diff"]; assert rd.texte([(j, ">", -1.0), (j, ">", 0.5), (j, "<=", 2.0), (j, "<=", 3.0)]) == ["0.500 < elo_diff <= 2.000"]
