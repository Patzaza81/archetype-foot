import json, numpy as np
import calibration_p1 as cp, calibration_finale as cf, pouvoir_predictif_v3 as v3

CFG = {"competitions": {"XX": {"ext": {"statut": "CORRECTION VALIDEE", "methode": "SLOPE", "parametres": {"a": 1.5, "b": -0.2, "c": 0.0}},
                               "dom": {"statut": "P1 CONSERVE", "methode": "P1", "parametres": None},
                               "nul": {"statut": "CORRECTION VALIDEE", "methode": "ELO_PALIER", "parametres": {"a": 1.0, "b": 0.0, "c": 0.0, "theta": -1.0, "r_bas": 0.2, "r_haut": -0.05, "palier": "elo"}}}}}

def test_p1_conserve_et_couple_absent_renvoient_p1():
    p = np.array([.2, .5, .8])
    for comp, m in (("XX", "dom"), ("XX", "btts"), ("YY", "ext")): q, info = cp.appliquer(CFG, comp, m, p); assert np.array_equal(q, p) and info["methode"] == "P1"

def test_correction_validee_applique_la_formule():
    p = np.array([.2, .5, .8]); q, info = cp.appliquer(CFG, "XX", "ext", p)
    assert np.allclose(q, 1 / (1 + np.exp(-(1.5 * np.log(p / (1 - p)) - 0.2)))) and info["methode"] == "SLOPE"
    q2, _ = cp.appliquer(CFG, "XX", "nul", np.array([.3, .3]), elo_diff=np.array([-2.0, 0.5])); assert np.allclose(q2, [.5, .25])
    try: cp.appliquer(CFG, "XX", "nul", p); raise AssertionError("elo_diff aurait du etre exige")
    except ValueError: pass

def test_1x2_renormalise_seulement_si_correction():
    a = cp.appliquer_1x2(CFG, "YY", .5, .3, .2); assert a == (.5, .3, .2) or np.allclose(a, (.5, .3, .2))
    b = cp.appliquer_1x2(CFG, "XX", np.array([.5]), np.array([.3]), np.array([.2]), elo_diff=np.array([0.0])); assert abs(sum(float(x[0]) for x in b) - 1) < 1e-9

def test_elo_module_identique_a_la_recherche():
    r = np.random.default_rng(1); eq = list("ABCDEFGH"); M = []
    for i in range(120):
        h, a = r.choice(eq, 2, replace=False); M.append((730000 + i // 4, "2122", str(h), str(a), int(r.poisson(1.5)), int(r.poisson(1.1))))
    X = v3.variables(M, 0.05, np.full((len(M), 2), 1.3))
    for k in (20, 77, 119): assert abs(X[k, 0] - cp.elo_diff_depuis_historique([(m[0], m[2], m[3], m[4], m[5]) for m in M if m[0] < M[k][0]], 0.05, M[k][2], M[k][3])) < 1e-12

def test_aucune_fuite_dans_la_calibration_de_la_saison_t():
    r = np.random.default_rng(0); n = 1500; S = np.repeat(np.arange(5), n // 5); D = 730000 + np.arange(n); p = np.clip(.4 + .1 * r.normal(size=n), .05, .95); y = (r.random(n) < p).astype(float); elo = r.normal(size=n)
    start = {s: D[S == s].min() for s in range(5)}; y2 = y.copy(); t = 3; y2[S >= t] = 1 - y2[S >= t]; v = np.ones(n, bool)
    for m in cf.METHODES:
        a = cf.prediction_saison(m, p, elo, y, v, S, D, start, t); b = cf.prediction_saison(m, p, elo, y2, v, S, D, start, t)
        assert np.allclose(a[1], b[1]) and a[2] == b[2]

def test_configuration_livree_coherente():
    C = cp.charger(); assert len(C["competitions"]) == 38
    for comp, v in C["competitions"].items():
        for m in cp.MARCHES:
            e = v[m]; assert e["statut"] in ("CORRECTION VALIDEE", "P1 CONSERVE")
            assert (e["statut"] == "CORRECTION VALIDEE") == (e["parametres"] is not None) == (e["methode"] != "P1")
            assert all(k in e for k in ("conditions_application", "couverture", "performances_par_saison", "confirmation_2526", "observation"))
