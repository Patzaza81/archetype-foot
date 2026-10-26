"""Découverte v2 : protocole propre à chaque marché (lecture seule)."""
import math
from pathlib import Path

import numpy as np

from alpha_serie import decouverte_marches as V1, decouverte_marches_v2 as V2
from alpha_serie.marches import test_du_marche as predicat

RACINE = Path(__file__).resolve().parent.parent


def test_effectif_exige_propre_au_marche():
    # petit écart sur marché fréquent : beaucoup de matchs ; grand écart : peu ; écart nul ou négatif : impossible
    assert V2.n_min(0.86, 0.90) > V2.n_min(0.86, 0.95) > 0
    assert V2.n_min(0.13, 0.16) > V2.n_min(0.13, 0.30)
    assert V2.n_min(0.5, 0.5) == math.inf and V2.n_min(0.5, 0.4) == math.inf and V2.n_min(0.5, 1.0) == math.inf
    # validité n·p ≥ 10 : un marché rare exige au moins 10 / p0
    assert V2.n_min(0.05, 0.5) >= math.ceil(10 / 0.05)
    # vectoriel = scalaire
    p1 = np.array([0.55, 0.6, 0.7, 0.9])
    assert list(V2.n_min_vec(0.5, p1)) == [V2.n_min(0.5, x) for x in p1]
    # plancher différent selon le marché
    assert len({V2.plancher(0.13), V2.plancher(0.5), V2.plancher(0.86)}) == 3


def test_niveaux_entre_taux_de_base_et_plus_haut_demontrable():
    e = V2.echelle(0.5, 0.7)
    assert len(e) == 10 and e[0] == 0.52 and e[-1] == 0.7 and all(0.5 < x <= 0.7 for x in e)


def _row(hm, hc, am, ac, niv=(1.5, 1.0)):
    return {"serie": (hm, hc, am, ac), "niv": niv}


def test_frequence_de_l_evenement_dans_les_series_3_passent_3_echouent():
    pred = predicat("handicap_-1.5", "domicile")          # l'équipe qui reçoit gagne par 2 buts ou plus
    # série domicile (marqués, encaissés) : 3-0 passe, 4-1 passe, 2-0 passe ; 2-1, 0-0, 1-3 échouent
    passe = V2.miroir([_row([3, 4, 2], [0, 1, 0], [0], [0])], pred)[0]
    echoue = V2.miroir([_row([2, 0, 1], [1, 0, 3], [0], [0])], pred)[0]
    assert passe[0] == 1.0 and echoue[0] == 0.0
    # série extérieur de l'équipe qui se déplace : (marqués 0, encaissés 2) = défaite 2-0 → l'événement (domicile gagne par 2+) a lieu
    ext_passe = V2.miroir([_row([0], [0], [0, 1, 0], [2, 3, 3])], pred)[0]
    ext_echoue = V2.miroir([_row([0], [0], [2, 1, 0], [0, 2, 1])], pred)[0]
    assert ext_passe[1] == 1.0 and ext_echoue[1] == 0.0
    assert ext_passe[2] == (0.0 + 1.0) / 2


def test_scenarios_et_poisson_du_marche():
    pred = predicat("over_under_2.5", "plus")
    # offensifs (hm, am) : 2+1, 0+0 ; défensifs (ac, hc) : 3+0, 1+0 → 2 sur 4
    r = V2.miroir([_row([2, 0], [0, 1], [1, 0], [3, 1], niv=(1.4, 1.1))], pred)[0]
    assert r[3] == 0.5
    pois = lambda l, k: math.exp(-l) * l ** k / math.factorial(k)
    attendu = sum(pois(1.4, h) * pois(1.1, a) for h in range(11) for a in range(11) if h + a >= 3)
    assert abs(r[4] - attendu) < 1e-9


def test_probabilite_implicite_cote_figee():
    evts = V1.evenements()
    rows = [{"cotes_brutes": {"1x2": {"1": 2.0, "N": 3.4, "2": 3.8}, "double_chance": {"1N": 1.25, "N2": 1.75, "12": 1.3}}}, {"cotes_brutes": {}}]
    p = [V2.proba_implicite(rows, evts[k])[0] for k in ("1x2|1", "1x2|N", "1x2|2")]
    assert abs(sum(p) - 1) < 1e-9 and p[0] > p[1]
    dc = [V2.proba_implicite(rows, evts[k])[0] for k in ("double_chance|1N", "double_chance|N2", "double_chance|12")]
    assert abs(sum(dc) - 2) < 1e-9                                  # chaque score est couvert deux fois
    assert np.isnan(V2.proba_implicite(rows, evts["1x2|1"])[1])      # pas de cote : NaN, jamais inventée


def test_seuils_pris_sur_le_reglage_seul_et_plancher_du_marche():
    rng = np.random.default_rng(0)
    per = np.repeat([0, 1, 2], 400)
    X = rng.integers(0, 8, size=(1200, 1)).astype(float) / 7
    a1, _ = V2.atomes(X, ["v"], per, 50)
    X2 = X.copy()
    X2[per == 2] = 0.123                                             # changer la période de contrôle ne change aucun seuil
    a2, _ = V2.atomes(X2, ["v"], per, 50)
    assert a1 == a2
    a3, _ = V2.atomes(X, ["v"], per, 150)
    assert len(a3) < len(a1)                                         # plancher plus haut (marché rare) : moins de seuils
    assert all(t in set(np.round(np.unique(X[per == 0]), 4)) for _, _, t in a1)


def test_etude_S_sans_cote_et_F_chronologique():
    rows = [{"jour": j, "serie": ([1], [0], [1], [1]), "niv": (1.2, 1.0), "cotes_brutes": {}, "h": 1, "a": 0}
            for j in ("2025-05-01", "2026-09-28", "2026-10-04", "2026-10-05", "2026-10-11", "2026-10-12", "2026-10-25")]
    d = {"rows": rows, "noms": ["h_gf", "m_ph", "x_tot"], "X": np.zeros((7, 3)), "periode": np.array([0, 3, 3, 3, 3, 3, 3])}
    e = V1.evenements()["1x2|1"]
    _, noms = V2.donnees_S(d, e)
    assert not any(n.startswith("m_") for n in noms) and set(V2.SPECIFIQUES) <= set(noms)
    _, nomsF = V2.donnees_F(d, e)
    assert "m_ph" in nomsF and "ev_cote_figee" in nomsF
    assert list(V2.periodes_F(d)) == [-1, 0, 0, 1, 1, 2, 2]


def test_jugement_effectif_planifie_et_statuts():
    n = 400
    per = np.repeat([0, 1, 2, 3], n)
    rows = [{"jour": "2026-05-01", "cotes": {}} for _ in range(4 * n)]
    y = np.zeros(4 * n, dtype=bool)
    sel = np.zeros(4 * n, dtype=bool)
    for p in range(3):
        idx = np.arange(p * n, p * n + 200)
        sel[idx] = True
        y[idx[:150]] = True                                          # 75 % avec la configuration
        y[p * n + 200: p * n + 260] = True                           # 30 % sans
    j = V2.juger(sel, y, per, rows, 0.7, 0.5, "x")
    assert j["statut"] == "confirmee" and j["effectif_exige_par_periode"] == V2.n_min(0.5, 0.7)
    sel2 = sel.copy()
    sel2[2 * n + 20: 2 * n + 200] = False                            # C n'a plus que 20 matchs : à confirmer, pas confirmée
    j2 = V2.juger(sel2, y, per, rows, 0.7, 0.5, "x")
    assert j2["statut"] == "a_confirmer"
    y3 = y.copy()
    y3[2 * n: 2 * n + 150] = False
    y3[2 * n: 2 * n + 80] = True                                     # 40 % sur C : sous le niveau → rejetée
    assert V2.juger(sel, y3, per, rows, 0.7, 0.5, "x")["statut"] == "rejetee"


def test_permutation_reproductible_et_dans_chaque_periode():
    per = np.repeat([0, 1, 2], 50)
    y = np.arange(150) % 3 == 0
    a, b = V2.permuter(y, per, 7), V2.permuter(y, per, 7)
    assert (a == b).all()
    for p in range(3):
        assert a[per == p].sum() == y[per == p].sum()


def test_non_branchee_a_la_production():
    for f in (RACINE / "alpha_serie").glob("*.py"):
        if f.name != "decouverte_marches_v2.py":
            assert "decouverte_marches_v2" not in f.read_text(encoding="utf-8"), f.name
    src = (RACINE / "alpha_serie" / "decouverte_marches_v2.py").read_text(encoding="utf-8")
    assert "journal.jsonl" not in src and "_ajouter" not in src and "geler(" not in src
