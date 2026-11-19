"""MEGAPOWER v2 (sans aucune cote) : modèle de buts, scénarios, calibrage, sélection, journal gelé. Données fabriquées, aucune donnée du jour."""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import verif_pronostic as V
from megapower import calibration as C, modele as M, suivi as SV


def rec(date, dom, adv, gf, ga, xgf=None, xga=None):
    return {"date": date, "dom": dom, "adv": adv, "gf": gf, "ga": ga, "xgf": xgf, "xga": xga}


def match(nd=5, ne=5, jour="2026-11-01", gf=1, ga=1):
    md = [rec(f"2026-10-{i + 1:02d}", True, "X", gf, ga) for i in range(nd)]
    me = [rec(f"2026-10-{i + 1:02d}", False, "Y", gf, ga) for i in range(ne)]
    return {"id": "m1", "jour": jour, "competition": "L", "saison": "2627", "cle_dom": "A", "cle_ext": "B", "domicile": "A", "exterieur": "B", "md": md, "me": me}


# ------------------------------------------------------------------ aucune cote nulle part
def test_aucune_cote_dans_le_code_du_moteur():
    for f in Path(M.__file__).parent.glob("*.py"):
        if f.name in ("tri_moteurs.py",):                       # tri des autres moteurs, ancien module non branché au moteur v2
            continue
        assert "cotes_betpawa" not in f.read_text(encoding="utf-8"), f.name


# ------------------------------------------------------------------ règle des 4 matchs au même lieu
def test_quatre_matchs_au_meme_lieu_acceptes():
    for nd, ne in ((4, 4), (5, 4), (6, 9)):
        lig = M.Ligue({})
        assert M.composantes(match(nd, ne), lig, 0.5, 4, 50) is not None


def test_moins_de_quatre_matchs_au_meme_lieu_rejetes():
    for nd, ne in ((3, 6), (6, 3), (0, 0)):
        lig = M.Ligue({})
        assert M.composantes(match(nd, ne), lig, 0.5, 4, 50) is None


def test_xg_absent_jamais_invente():
    r = rec("2026-10-01", True, "X", 2, 1)
    assert M._obs(r, "f", 1.0) == 2.0 and M._obs(r, "a", 1.0) == 1.0          # xG manquant : les buts seuls
    r2 = rec("2026-10-01", True, "X", 2, 1, 1.0, 0.4)
    assert M._obs(r2, "f", 1.0) == 1.0 and M._obs(r2, "f", 0.0) == 2.0 and abs(M._obs(r2, "a", 0.5) - 0.7) < 1e-9


# ------------------------------------------------------------------ anti-fuite : les notes d'une ligue n'utilisent que les matchs d'avant
def test_notes_de_ligue_sans_fuite():
    eq = {"A": {"2026-10-01": rec("2026-10-01", True, "B", 5, 0), "2026-10-20": rec("2026-10-20", True, "B", 0, 9)}}
    lig = M.Ligue(eq)
    avant = lig.notes("2026-10-10", 0.0, 4, 0)
    assert avant["n"] == 1 and abs(avant["mu_h"] - 5.0) < 1e-9                  # le match du 20 n'entre pas
    assert lig.notes("2026-10-01", 0.0, 4, 0)["n"] == 0                          # le jour même : rien


# ------------------------------------------------------------------ probabilités et scénarios
def test_probabilites_coherentes():
    p = M.probas(np.array([1.6]), np.array([1.1]))[0]
    i = V.IDX
    assert abs(p[i["1"]] + p[i["N"]] + p[i["2"]] - 1) < 1e-9
    assert abs(p[i["btts_oui"]] + p[i["btts_non"]] - 1) < 1e-9
    assert p[i["total_plus_1.5"]] > p[i["total_plus_2.5"]] > p[i["total_plus_3.5"]]


def test_scenario_catastrophe_jamais_au_dessus_du_normal_ni_du_favorable():
    n, f, c = M.scenarios([1.6, 0.9], [1.1, 1.4], [0.15, 0.2], [0.1, 0.3])
    assert (c <= n + 1e-12).all() and (n <= f + 1e-12).all() and (c < f).any()


# ------------------------------------------------------------------ sélection : jamais deux fois le même événement


def test_selection_garde_le_plus_precis():
    q = np.full(len(V.NOMS), 0.5)
    for n, v in (("total_plus_0.5", 0.95), ("total_plus_1.5", 0.85), ("1N", 0.90), ("1", 0.75), ("N2", 0.8)):
        q[V.IDX[n]] = v
    ok = q >= 0.72
    got = [V.NOMS[k] for k in C.choisir(q, ok)]
    assert "total_plus_1.5" in got and "total_plus_0.5" not in got               # 1,5 implique 0,5 : on garde le précis
    assert "1" in got and "1N" not in got                                        # victoire implique double chance
    assert "N2" in got                                                            # sans lien avec les autres : gardé
    assert got == sorted(got, key=lambda n: -q[V.IDX[n]])                        # classé du plus fiable au moins fiable


def test_selection_ne_retient_rien_sous_la_barre():
    q = np.full(len(V.NOMS), 0.6)
    assert C.choisir(q, q >= 0.72) == []
    q2 = q.copy(); q2[V.IDX["btts_oui"]] = np.nan
    assert C.choisir(np.nan_to_num(q2), ~np.isnan(q2) & (q2 >= 0.72)) == []


def test_seuil_borne_basse_et_familles():
    n = len(V.NOMS)
    q, bas = np.full(n, 0.9), np.full(n, 0.9)
    bas[V.IDX["total_plus_1.5"]] = 0.70                                          # fiable en moyenne mais borne basse trop basse : rejeté
    got = {V.NOMS[k] for k in SV.retenus(bas, q, 0.72)}
    assert "total_plus_1.5" not in got and got
    got2 = {V.NOMS[k] for k in SV.retenus(bas, q, 0.72, {"cage inviolée"})}       # seule la famille autorisée passe
    assert got2 and all(C.famille(x) == "cage inviolée" for x in got2)
    assert SV.retenus(np.full(n, np.nan), q, 0.72) == []                          # famille jamais apprise : jamais retenu


def test_famille_de_chaque_marche_du_catalogue():
    assert all(C.famille(n) in C.FAMILLES for n in V.NOMS)
    assert C.famille("1N&total_plus_1.5") == "double chance + total de buts" and C.famille("2") == "victoire ou nul" and C.famille("cage_dom_oui") == "cage inviolée"


# ------------------------------------------------------------------ calibrage
def test_calibrage_corrige_une_probabilite_trop_optimiste():
    rng = np.random.default_rng(1)
    n = 4000
    pn = rng.uniform(0.5, 0.95, n)
    y = (rng.uniform(size=n) < pn - 0.15).astype(float)                          # la réalité est 15 points sous le modèle
    marche = np.full(n, V.IDX["total_plus_1.5"])
    cal = C.apprendre(pn, pn, y, marche, np.arange(n))
    q, bas = C.predire(cal, np.array([0.9]), np.array([0.9]), np.array([V.IDX["total_plus_1.5"]]))
    assert abs(q[0] - 0.75) < 0.05 and bas[0] < q[0]


# ------------------------------------------------------------------ journal gelé
def _fiche(mid, ko, paris):
    return {"match_id": mid, "jour": ko[:10], "coup_d_envoi_utc": ko, "domicile": "A", "exterieur": "B", "paris": paris}


def _pari(marche="total_plus_1.5", q=0.8):
    return {"marche": marche, "libelle": marche, "famille": C.famille(marche), "fiabilite": q, "fiabilite_basse": q - 0.03, "modele": q, "catastrophe": q - 0.1, "favorable": q + 0.05}


def test_gel_avant_le_coup_d_envoi_seulement(tmp_path):
    j = tmp_path / "j.jsonl"
    ko = "2026-11-20T15:00:00+00:00"
    avant, apres = datetime(2026, 11, 20, 10, tzinfo=timezone.utc), datetime(2026, 11, 20, 16, tzinfo=timezone.utc)
    SV._ajouter(j, [{"type": "pronostic", "match_id": "m1", "gele_le": avant.isoformat(), "fiche": _fiche("m1", ko, [_pari()])},
                    {"type": "pronostic", "match_id": "m2", "gele_le": apres.isoformat(), "fiche": _fiche("m2", ko, [_pari()])}])
    v = SV.gels_valides(SV._lire(j))
    assert "m1" in v and "m2" not in v                                            # un gel fait après le coup d'envoi ne compte jamais


def test_reglement_et_bilan(tmp_path):
    j = tmp_path / "j.jsonl"
    ko = "2026-11-20T15:00:00+00:00"
    SV._ajouter(j, [{"type": "pronostic", "match_id": "m1", "gele_le": "2026-11-20T10:00:00+00:00", "fiche": _fiche("m1", ko, [_pari("total_plus_1.5", 0.8), _pari("1", 0.75)])}])
    assert SV.resultats({"m1": (2, 0)}, j) == 1
    assert SV.resultats({"m1": (2, 0)}, j) == 0                                   # réglé une seule fois
    b = SV.bilan(SV._lire(j))
    assert b["pronostics"] == 2 and b["matchs"] == 1 and b["reussite"] == 1.0 and abs(b["fiabilite_annoncee"] - 0.775) < 1e-9
    j2 = tmp_path / "j2.jsonl"
    SV._ajouter(j2, [{"type": "pronostic", "match_id": "m1", "gele_le": "2026-11-20T10:00:00+00:00", "fiche": _fiche("m1", ko, [_pari("total_plus_1.5", 0.8), _pari("1", 0.75)])}])
    SV.resultats({"m1": (0, 0)}, j2)
    b2 = SV.bilan(SV._lire(j2))
    assert b2["reussite"] == 0.0                                                  # 0-0 : ni plus de 1,5 ni victoire


def test_aucun_pronostic_est_valide(tmp_path):
    j = tmp_path / "j.jsonl"
    SV._ajouter(j, [{"type": "pronostic", "match_id": "m1", "gele_le": "2026-11-20T10:00:00+00:00", "fiche": _fiche("m1", "2026-11-20T15:00:00+00:00", [])}])
    assert SV.resultats({"m1": (1, 1)}, j) == 0 and SV.bilan(SV._lire(j)) == {"pronostics": 0, "matchs": 0}
