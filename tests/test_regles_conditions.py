import numpy as np
import regles_conditions as rc

def _PR(seed=0, n=1500):
    r = np.random.default_rng(seed); S = np.repeat(np.arange(5), n // 5); D = 730000 + np.arange(n)
    X = r.normal(size=(n, 18)); p = np.clip(0.5 + 0.1 * r.normal(size=(n, 7)), 0.05, 0.95)
    Y = (r.random((n, 7)) < p + 0.15 * (X[:, [0]] > 0.5)).astype(float)
    return dict(S=S, D=D, Y=Y, valide=np.ones(n, bool), P1=p, X=X, start={s: D[S == s].min() for s in range(5)})

def test_regles_gelees_independantes_de_la_saison_test_et_du_futur():
    PR = _PR(); PR2 = {k: (v.copy() if hasattr(v, "copy") else v) for k, v in PR.items()}
    s = 3; cut = PR["start"][s]; PR2["Y"][PR["D"] >= cut] = 1 - PR2["Y"][PR["D"] >= cut]
    a = rc.regles_avant(PR, 0, s, {}); b = rc.regles_avant(PR2, 0, s, {})
    assert [q["cond"] for q in a] == [q["cond"] for q in b] and [q["r"] for q in a] == [q["r"] for q in b]

def test_lambda_choisi_sans_la_saison_test():
    PR = _PR(); PR2 = {k: (v.copy() if hasattr(v, "copy") else v) for k, v in PR.items()}
    s = 4; PR2["Y"][PR["S"] == s] = 1 - PR2["Y"][PR["S"] == s]
    assert rc.rejeu_marche(PR, 0, s)[1:] == rc.rejeu_marche(PR2, 0, s)[1:]

def test_decouvre_un_vrai_signal_et_pas_de_bruit():
    PR = _PR(); tr = PR["D"] < PR["start"][4]
    reg = rc.decouvrir(PR["X"][tr], PR["Y"][tr, 0], PR["P1"][tr, 0], PR["S"][tr])
    assert any(j == 0 for q in reg for j, o, th in q["cond"])           # la variable 0 porte le signal
    bruit = _PR(); bruit["Y"] = (np.random.default_rng(5).random(bruit["Y"].shape) < bruit["P1"]).astype(float)
    assert len(rc.decouvrir(bruit["X"][tr], bruit["Y"][tr, 0], bruit["P1"][tr, 0], bruit["S"][tr])) < len(reg)

def test_application_sens_et_couverture():
    X = np.zeros((4, 18)); X[:, 0] = [0, 1, 2, 3]; p = np.full(4, 0.5)
    q = {"cond": [(0, ">", 1.5)], "r": 0.1, "n": 10, "frac": 1.0}
    pc, cv = rc.ajuster_p([q], X, p, 1.0)
    assert list(cv) == [False, False, True, True] and np.allclose(pc, [0.5, 0.5, 0.6, 0.6])
    assert np.allclose(rc.ajuster_p([q], X, p, 0.0)[0], p)
    q2 = dict(q, frac=0.2)
    assert not rc.ajuster_p([q2], X, p, 1.0, fmin=0.5)[1].any() and rc.ajuster_p([q], X, p, 1.0, fmin=0.5)[1].any()
