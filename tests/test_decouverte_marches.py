"""Découverte marché par marché (lecture seule) : même logique que l'étude des victoires, démontrée par des tests (planté / bruit, chronologie, fuite, doublons)."""
from __future__ import annotations

import copy
import random
from pathlib import Path

import numpy as np
import pytest

from alpha_serie import coeur, decouverte_marches as DM, parametres as P, robustesse as RB, suivi as S

RACINE = Path(__file__).resolve().parent.parent


# ---------- jeu synthétique : un signal planté dans f0, f1/f2 = bruit ----------
def synth(planter: bool, n_par=(1500, 1000, 1500, 400), graine=3):
    rnd = np.random.default_rng(graine)
    per = np.concatenate([np.full(n, p) for p, n in enumerate(n_par)])
    N = len(per)
    f0, f1, f2 = rnd.random(N), rnd.random(N), rnd.random(N)
    p = 0.35 + (0.55 * (f0 > 0.6) if planter else 0.0)
    y = rnd.random(N) < p
    rows = [{"jour": "2025-06-01" if q == 0 else ("2026-02-01" if q == 1 else ("2026-06-01" if q == 2 else "2026-10-05")), "cotes": {}} for q in per]
    X = np.column_stack([f0, f1, f2])
    return {"X": X, "noms": ["f0", "f1", "f2"], "periode": per, "rows": rows, "H": np.where(y, 2, 0), "A_": np.zeros(N, dtype=int)}, y


def test_atomes_pris_sur_A_seule():
    d, y = synth(True)
    d2 = copy.deepcopy(d)
    d2["X"][d2["periode"] >= 1] = 99.0                    # B, C, D bouleversés : les seuils ne doivent pas bouger
    a1, _ = DM.atomes(d["X"], d["noms"], d["periode"])
    a2, _ = DM.atomes(d2["X"], d2["noms"], d2["periode"])
    assert a1 == a2


def test_configurations_egales_au_calcul_brut():
    d, y = synth(True)
    at, M = DM.atomes(d["X"], d["noms"], d["periode"])
    c = DM.configurations(M, y, d["periode"], {})
    rnd = random.Random(1)
    for t in rnd.sample(range(len(c["conds"])), 25):
        sel = DM.masque(M, c["conds"][t])
        assert c["nA"][t] == (sel & (d["periode"] == 0)).sum() and c["kA"][t] == (sel & (d["periode"] == 0) & y).sum()
        assert c["nB"][t] == (sel & (d["periode"] == 1)).sum() and c["kB"][t] == (sel & (d["periode"] == 1) & y).sum()


def test_signal_plante_retrouve_et_confirme_sur_C():
    d, y = synth(True)
    r = DM.etudier(d, {"x": {"nom": "x", "cles": [("x", "x")], "pred": lambda h, a: h > a}}, signal=False)["x"]
    conf = [f for f in r["frontiere"] if f["statut"] == "confirmee_sur_C"]
    assert conf and any("f0" in f["configuration"] for f in conf)
    f = conf[-1]
    assert f["C"]["taux"] > f["C"]["reference_matchs_sans_la_configuration"]["taux"] + 0.2


def test_bruit_pur_ne_confirme_rien_a_haut_niveau():
    d, y = synth(False)
    r = DM.etudier(d, {"x": {"nom": "x", "cles": [("x", "x")], "pred": lambda h, a: h > a}}, signal=False)["x"]
    assert not any(f["statut"] == "confirmee_sur_C" and f["niveau_vise"] >= 0.5 for f in r["frontiere"])


def test_le_choix_ne_lit_ni_C_ni_D():
    d, y = synth(True)
    evt = {"x": {"nom": "x", "cles": [("x", "x")], "pred": lambda h, a: h > a}}
    d2 = copy.deepcopy(d)
    rnd = np.random.default_rng(9)
    m = d2["periode"] >= 2
    d2["H"][m] = rnd.integers(0, 3, m.sum())              # résultats de C et D remplacés
    r1 = DM.etudier(d, evt, signal=False)["x"]["frontiere"]
    r2 = DM.etudier(d2, evt, signal=False)["x"]["frontiere"]
    assert [f["configuration"] for f in r1] == [f["configuration"] for f in r2]


def test_permutation_conserve_les_effectifs_de_chaque_periode():
    d, y = synth(True)
    evt = {"x": {"nom": "x", "cles": [("x", "x")], "pred": lambda h, a: h > a}}
    yp = DM.permuter(d, evt, 5)["x"]
    for p in range(4):
        assert yp[d["periode"] == p].sum() == y[d["periode"] == p].sum()
    assert (yp != y).any()


def test_statuts_trois_cas_confirmes_trois_rejetes():
    def sel_y(n_in, g_in, n_out, g_out):
        per = np.full(n_in + n_out, 2)
        sel = np.arange(n_in + n_out) < n_in
        y = np.zeros(n_in + n_out, dtype=bool)
        y[:g_in] = True
        y[n_in:n_in + g_out] = True
        return sel, y, per
    rows = lambda n: [{"jour": "2026-06-01", "cotes": {}} for _ in range(n)]
    def statut(*a, niv=0.7):
        sel, y, per = sel_y(*a)
        per2 = np.concatenate([np.zeros(10, int), np.ones(10, int), per, np.full(5, 3)])
        sel2 = np.concatenate([np.zeros(20, bool), sel, np.zeros(5, bool)])
        y2 = np.concatenate([np.zeros(20, bool), y, np.zeros(5, bool)])
        # A+B neutres : on teste le jugement sur C seul (baisse non testable avec A+B quasi vides)
        return DM.juger(sel2, y2, per2, rows(len(per2)), niv, "x", 180, 28)["statut"]
    assert statut(300, 240, 300, 120) == "confirmee_sur_C"        # 80 % contre 40 % ailleurs
    assert statut(200, 150, 400, 160) == "confirmee_sur_C"        # 75 % contre 40 %
    assert statut(150, 120, 500, 250, niv=0.75) == "confirmee_sur_C"
    assert statut(300, 150, 300, 150) == "rejetee"                 # pas mieux qu'ailleurs
    assert statut(300, 180, 300, 90, niv=0.8) == "rejetee"         # 60 % : significativement sous 80 %
    assert statut(10, 10, 300, 100) == "rejetee"                   # effectif insuffisant (< 30)
    assert statut(60, 50, 500, 200) == "prometteuse_a_confirmer"   # 30 <= n < 100, signal sans contre-indication


# ---------- événements, fuite, doublons, jeux (données réelles) ----------
def test_evenements_sans_doublon_de_table_de_verite():
    ev = DM.evenements()
    assert len(ev) == len({tuple(bool(e["pred"](h, a)) for h in range(10) for a in range(10)) for e in ev.values()})
    assert ("handicap_-0.5", "domicile") in ev["1x2|1"]["cles"]                   # même événement que la victoire du domicile
    assert ("double_chance", "N2") in ev["double_chance|N2"]["cles"]
    assert "double_chance|12" in ev and "over_under_3.5|moins" in ev


@pytest.fixture(scope="module")
def donnees():
    ev = DM.evenements()
    return ev, DM.construire(ev)


def test_jeux_disjoints_et_sans_resultat_manquant(donnees):
    ev, d = donnees
    ids = [r["id"] for r in d["rows"]]
    assert len(ids) == len(set(ids)) and d["audit"]["resultats_manquants"] == d["audit"]["ids_en_double"] == d["audit"]["matchs_en_double_meme_source"] == 0
    per = d["periode"]
    assert all(r["jour"] < DM.DEBUT_D for r, p in zip(d["rows"], per) if p < 3) and all(r["src"] == "ARCH" for r, p in zip(d["rows"], per) if p == 3)
    assert all(r["jour"] < DM.FIN_A for r, p in zip(d["rows"], per) if p == 0) and all(DM.FIN_A <= r["jour"] < DM.FIN_B for r, p in zip(d["rows"], per) if p == 1)
    assert all(DM.FIN_B <= r["jour"] < DM.DEBUT_D for r, p in zip(d["rows"], per) if p == 2)


def test_caracteristiques_insensibles_aux_matchs_futurs():
    params = P.charger()
    for m in (x for x in RB.charger_archive_archetype() if x["jour"] == "2026-10-10"):
        r = coeur.analyser_match(m["dom"], m["ext"], m["jour"], params)
        if r["statut"] == "analyse":
            break
    hm, hc = coeur.serie_lieu(m["dom"], True, m["jour"])
    d = copy.deepcopy(m["dom"])
    d["matchs"].append({"date": "2026-10-11", "domicile": True, "buts_marques": 9, "buts_encaisses": 9})
    d["matchs"].append({"date": m["jour"], "domicile": True, "buts_marques": 7, "buts_encaisses": 7})      # le jour même : exclu aussi
    assert coeur.serie_lieu(d, True, m["jour"]) == (hm, hc)


def test_caracteristiques_calculs_connus():
    f = DM.caracteristiques([2, 0, 3], [1, 0, 1], [1, 1, 0], [2, 3, 0], {"dom": 1.2, "ext": 1.0, "total": 2.2, "d": 0.2}, [(2, 1)], [(2, 1)], [2.0, 3.0, 4.0], [1.8, 2.0])
    assert f["h_gf"] == pytest.approx(5 / 3) and f["h_vic"] == pytest.approx(2 / 3) and f["h_nul"] == pytest.approx(1 / 3) and f["h_cs"] == pytest.approx(1 / 3)
    assert f["a_def"] == pytest.approx(2 / 3) and f["a_fts"] == pytest.approx(1 / 3)
    assert f["h_o25"] == pytest.approx(2 / 3) and f["h_btts"] == pytest.approx(2 / 3) and f["h_o35"] == pytest.approx(1 / 3)
    assert f["m_ph"] + f["m_pn"] + f["m_pa"] == pytest.approx(1) and f["m_p1n"] == pytest.approx(f["m_ph"] + f["m_pn"])
    assert f["m_pover25"] == pytest.approx((1 / 1.8) / (1 / 1.8 + 1 / 2.0))
    assert DM.caracteristiques([1], [1], [1], [1], {"dom": 1, "ext": 1, "total": 2, "d": 0}, [(1, 1)], [(1, 1)], None, None)["m_ph"] != DM.caracteristiques([1], [1], [1], [1], {"dom": 1, "ext": 1, "total": 2, "d": 0}, [(1, 1)], [(1, 1)], None, None)["m_ph"]  # NaN


def test_imposes_traites_par_la_meme_fonction_et_rejetables(donnees):
    ev, d = donnees
    res = DM.evaluer_imposes(d, ev)
    assert set(res) == set(DM.CANDIDATS_IMPOSES) and all(r["statut"] in ("confirmee_sur_C", "prometteuse_a_confirmer", "rejetee") for r in res.values())
    for eid, conds in DM.CANDIDATS_IMPOSES.items():
        y = DM.gagnants(d, ev[eid])
        sel = DM.masque_conditions(d, conds)
        assert res[eid] == {**DM.juger(sel, y, d["periode"], d["rows"], DM.niveau_promis(sel, y, d["periode"]), eid, 180, 28), "configuration": res[eid]["configuration"], "nom": res[eid]["nom"], "note": res[eid]["note"]}


def test_jamais_valide_et_non_branche_a_la_production(donnees):
    ev, d = donnees
    r = DM.etudier(d, {k: ev[k] for k in ("over_under_3.5|moins", "double_chance|12")}, signal=False)
    assert all(f["statut"] in ("confirmee_sur_C", "prometteuse_a_confirmer", "rejetee") for m in r.values() for f in m["frontiere"])
    for f in (RACINE / "alpha_serie").glob("*.py"):
        if f.name not in ("decouverte_marches.py", "etude_marches.py", "decouverte_marches_v2.py"):
            assert "decouverte_marches" not in f.read_text(encoding="utf-8"), f.name
    src = (RACINE / "alpha_serie" / "decouverte_marches.py").read_text(encoding="utf-8")
    assert "journal.jsonl" not in src and "_ajouter" not in src and "geler(" not in src


def test_wilson_du_module_identique_a_celui_du_suivi():
    for g, n in ((0, 10), (7, 10), (70, 100), (845, 1000)):
        assert round(DM.wilson(g, n)[0], 4) == S.wilson_bas(g, n)
