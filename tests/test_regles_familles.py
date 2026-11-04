import numpy as np
import regles_familles as rf, regles_durables as rd, approfondissement as ap

def _rule(mem, r, z=3.0, ev_r=0.1):
    return {"cond": [(0, ">", 0.0)], "r": r, "mem": mem, "ev": {"z": z, "r_ev": ev_r, "ev": [], "ok_all": True}}

def test_familles_regroupe_recouvrement_et_signe():
    n = 400; y = np.zeros(n); p = np.full(n, .5); var = p * (1 - p); valide = np.ones(n, bool)
    a = np.zeros(n, bool); a[:200] = True; b = np.zeros(n, bool); b[:160] = True; c = np.zeros(n, bool); c[300:] = True; d = a.copy()
    F = rf.familles([_rule(a, .1, 4), _rule(b, .1, 3), _rule(c, .1, 2), _rule(d, -.1, 2)], valide, y, p, var)
    assert len(F) == 3                                                    # a+b ensemble ; c et d (signe oppose) separes
    assert max(F, key=lambda f: f["rep"]["ev"]["z"])["rep"]["ev"]["z"] == 4
    assert any(f["membres"] and f["membres"][0]["role"] == "redondante" for f in F)

def test_raffinement_detecte_si_le_sous_ensemble_est_plus_fort():
    n = 600; r = np.random.default_rng(0); p = np.full(n, .5); var = p * (1 - p); valide = np.ones(n, bool)
    rep = np.zeros(n, bool); rep[:400] = True; sous = np.zeros(n, bool); sous[:150] = True
    y = np.where(sous, (r.random(n) < .8), (r.random(n) < .5)).astype(float)
    F = rf.familles([_rule(rep, .1, 4), _rule(sous, .3, 3)], valide, y, p, var)
    assert len(F) == 1 and F[0]["membres"][0]["role"] == "raffinement"

def test_regles_validees_independantes_des_saisons_non_ecoulees():
    PR = rd._PR if hasattr(rd, "_PR") else None
    import tests.test_regles_durables as T
    PR = T._PR(); PR2 = {k: (v.copy() if hasattr(v, "copy") else v) for k, v in PR.items()}
    t = 3; PR2["Y"][PR["S"] >= t] = 1 - PR2["Y"][PR["S"] >= t]
    e = 0; R1 = rd.ensembles(PR, e); R2 = rd.ensembles(PR2, e); S, v = PR["S"], PR["valide"]
    for q1, q2 in zip(R1[t], R2[t]):
        assert q1["cond"] == q2["cond"]
    y, p = PR["Y"][:, e], PR["P1"][:, e]; y2 = PR2["Y"][:, e]
    a = [x["ev"]["r_ev"] for x in rf.validees(R1, t, "legere", v, S, y, p, p * (1 - p))]
    b = [x["ev"]["r_ev"] for x in rf.validees(R2, t, "legere", v, S, y2, p, p * (1 - p))]
    assert a == b                                                         # ancetres evalues sur des saisons < t seulement

def test_correction_moyenne_et_somme():
    X = np.zeros((3, len(rd.NOMS) - 1)); X[:, 0] = [0, 1, 2]; p = np.full(3, .5)
    f1 = _rule(None, .1, ev_r=0.1); f1["cond"] = [(0, ">", 0.5)]; f2 = _rule(None, .1, ev_r=0.3); f2["cond"] = [(0, ">", 1.5)]
    pm, cm = rf.corr([{"rep": f1}, {"rep": f2}], X, p, "moy"); ps, _ = rf.corr([{"rep": f1}, {"rep": f2}], X, p, "somme")
    assert np.allclose(pm, [.5, .6, .7]) and np.allclose(ps, [.5, .6, .9]) and list(cm) == [False, True, True]

def test_masque_texte():
    X = np.zeros((3, len(rd.NOMS) - 1)); j = rd.IDX["elo_diff"]; X[:, j] = [-2, -1, 0.5]
    assert list(ap.masque_texte(["elo_diff <= -1.090"], X)) == [True, False, False]
    assert list(ap.masque_texte(["-1.500 < elo_diff <= 0.600"], X)) == [False, True, True]
