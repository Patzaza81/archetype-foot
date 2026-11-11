import copy, json, os, numpy as np
import calibration_p1 as cp, integration_calibration as ic, pouvoir_predictif as pp

CFG = cp.charger()

def _fx(code="E0"):
    h = ic.historique(code); j = h[-1][0] + 1; return h, (j, h[-1][2], h[-1][3])

def test_config_competitions_fd_plus_matchendirect_7_marches():      # 38 divisions Football-Data + 8 championnats Matchendirect (p1_source_med)
    assert len(CFG["competitions"]) == 38 + len(ic.pm.COMPETITIONS_MED) and all(set(ic.MARCHES) <= set(v) and "p1" in v for v in CFG["competitions"].values())

def test_p1_futur_independant_du_score_fictif_et_des_autres_matchs_du_jour():
    h, f = _fx(); cfg = CFG["competitions"]["E0"]["p1"]
    a = ic.p1_matchs(h, [f], cfg)[f]; autre = (f[0], h[-5][2], h[-5][3])
    b = ic.p1_matchs(h, [f, autre], cfg)[f]; assert np.array_equal(a, b)
    ref = pp.predire(h + [(f[0], "futur", f[1], f[2], 9, 9)], "P1", cfg["k"], cfg["demi_vie_jours"])[-1]; assert np.array_equal(a, ref)

def test_historique_sans_fuite():
    h = ic.historique("E0", jusqua_jour=ic.historique("E0")[-1][0]); assert all(m[0] < h[-1][0] + 1 for m in h) and max(m[0] for m in h) < ic.historique("E0")[-1][0]

def test_parallele_identite_exacte_et_1x2_coherent():
    m = [{"match_id": "t1", "date": "2026-11-05", "coup_d_envoi_utc": "2026-11-05T19:00:00Z", "competition": "x", "domicile": "a", "exterieur": "b", "division": "E0", "fd_dom": ic.historique("E0")[-1][2], "fd_ext": ic.historique("E0")[-1][3]}]
    r = ic.traiter(m, CFG, "parallele")[0]; assert r["statut"] == "OK" and r["p1_calibre"] == r["p1_original"] and r["publie"] == r["p1_original"] and abs(r["somme_1x2_calibre"] - 1) < 1e-9

def test_hors_perimetre_et_division_inconnue():
    m = [{"match_id": "t2", "date": "2026-11-05", "coup_d_envoi_utc": None, "competition": "c", "domicile": "a", "exterieur": "b", "division": None, "fd_dom": None, "fd_ext": None}]
    assert ic.traiter(m, CFG)[0]["statut"] == "HORS_PERIMETRE"

def test_correction_validee_active_seulement_en_mode_actif_et_1x2_renormalise():
    c = copy.deepcopy(CFG); c["competitions"]["E0"]["ext"] = {"statut": "CORRECTION VALIDEE", "methode": "SLOPE", "parametres": {"a": 1.3, "b": 0.1, "c": 0.0}}
    d = ic.historique("E0")[-1]; m = [{"match_id": "t3", "date": "2026-11-05", "coup_d_envoi_utc": None, "competition": "x", "domicile": "a", "exterieur": "b", "division": "E0", "fd_dom": d[2], "fd_ext": d[3]}]
    for mode_ in ("parallele", "actif"):
        r = ic.traiter(m, c, mode_)[0]; assert r["p1_calibre"]["ext"] != r["p1_original"]["ext"] and abs(r["somme_1x2_calibre"] - 1) < 1e-9
        assert r["publie"] == (r["p1_calibre"] if mode_ == "actif" else r["p1_original"]); assert r["p1_calibre"]["o25"] == r["p1_original"]["o25"]

def test_journal_gele_non_reecrit(tmp_path):
    e = [{"statut": "OK", "match_id": "z", "coup_d_envoi_utc": "2099-01-01T00:00:00Z", "p1_original": {}, "p1_calibre": {}}]
    assert ic.ecrire(e, CFG, str(tmp_path))[0] == 1 and ic.ecrire(e, CFG, str(tmp_path))[0] == 0
    assert len(open(tmp_path / "journal.jsonl").read().strip().split("\n")) == 1

def test_mode_par_defaut_parallele(tmp_path):
    assert ic.mode(str(tmp_path / "absent.json")) == "parallele"
    p = tmp_path / "i.json"; p.write_text(json.dumps({"mode": "n_importe_quoi"})); assert ic.mode(str(p)) == "parallele"
