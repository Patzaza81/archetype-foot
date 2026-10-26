"""Validation des bandes de cotes 1X2 (26/10/2026) : gel avant le match, pertes comprises, sans doublon, sans effet sur Alpha."""
import json
from datetime import datetime, timezone

from alpha_serie import suivi as S

NUIT = datetime(2026, 11, 2, 1, 0, tzinfo=timezone.utc)


def match(i, c1=None, c2=None, ko="2026-11-02T14:00:00Z", date="2026-11-02", score=None):
    return {"match_id": "m%d" % i, "date": date, "coup_d_envoi_utc": ko, "competition": "Test", "domicile": "D%d" % i, "exterieur": "E%d" % i,
            "cotes_betpawa": {"1x2": {"1": c1, "2": c2, "N": 3.4}} if c1 or c2 else {}, "assemblage": {}, "score_final": score}


def gel(tmp_path, matchs, quand=NUIT):
    j = tmp_path / "j.jsonl"
    return j, S.geler_bandes(quand, j, matchs, params={})


def test_bornes_domicile_incluses_et_hors_bande(tmp_path):
    ok = [match(1, 1.33, 9), match(2, 1.50, 9), match(3, 1.40, 9)]
    ko = [match(4, 1.32, 9), match(5, 1.51, 9), match(6, 2.0, 9)]
    j, n = gel(tmp_path, ok + ko)
    assert n == 3 and {l["match_id"] for l in S._lire(j)} == {"m1", "m2", "m3"}


def test_bornes_exterieur_incluses_et_hors_bande(tmp_path):
    ok = [match(1, 9, 1.38), match(2, 9, 1.70), match(3, 9, 1.55)]
    ko = [match(4, 9, 1.37), match(5, 9, 1.71), match(6, 9, 2.5)]
    j, n = gel(tmp_path, ok + ko)
    assert n == 3 and {(l["match_id"], l["regle"]) for l in S._lire(j)} == {("m1", "exterieur"), ("m2", "exterieur"), ("m3", "exterieur")}


def test_un_match_peut_entrer_dans_les_deux_regles_sans_doublon(tmp_path):
    j, n = gel(tmp_path, [match(1, 1.45, 1.60)])
    assert n == 2
    assert S.geler_bandes(NUIT, j, [match(1, 1.45, 1.60)], params={}) == 0          # jamais regelé
    assert S.bilan_bandes(j, ecrire=False)["controles"]["doublons_match_regle"] == 0


def test_cotes_absentes_ou_invalides_ignorees(tmp_path):
    j, n = gel(tmp_path, [match(1), match(2, True, "x"), match(3, 0.0, 1.0)])
    assert n == 0


def test_aucun_gel_apres_le_coup_d_envoi_ni_si_score_connu(tmp_path):
    j, n = gel(tmp_path, [match(1, 1.4, 9, ko="2026-11-02T00:30:00Z"), match(2, 1.4, 9, score={"buts_dom": 1, "buts_ext": 0})])
    assert n == 0


def test_resultats_pertes_comprises_et_bilan(tmp_path):
    ms = [match(i, 1.4, 9, date="2026-11-02") for i in range(1, 5)] + [match(5, 9, 1.5, date="2026-11-09", ko="2026-11-09T14:00:00Z")]
    j, _ = gel(tmp_path, ms)
    fini = [dict(m) for m in ms]
    for m, sc in zip(fini, [(2, 0), (0, 0), (1, 3), (3, 1), (0, 1)]):
        m["score_final"] = {"buts_dom": sc[0], "buts_ext": sc[1]}
    assert S.resultats_bandes(j, fini) == 5 and S.resultats_bandes(j, fini) == 0
    b = S.bilan_bandes(j, ecrire=False)
    d, e = b["regles"]["domicile"], b["regles"]["exterieur"]
    assert (d["cumule"]["matchs"], d["cumule"]["gagnes"], d["cumule"]["perdus"]) == (4, 2, 2)
    assert (e["cumule"]["matchs"], e["cumule"]["gagnes"]) == (1, 1)
    assert d["par_semaine"]["2026-S45"]["matchs"] == 4 and e["par_semaine"]["2026-S46"]["gagnes"] == 1
    assert b["controles"] == {"doublons_match_regle": 0, "gels_non_anterieurs_au_coup_d_envoi": 0, "resultats_sans_gel": 0, "cotes_hors_bande": 0}


def test_wilson():
    assert S.wilson_bas(0, 0) is None
    assert abs(S.wilson_bas(68, 94) - 0.626) < 0.001 and S.wilson_bas(10, 10) < 1


def test_en_attente_et_bornes_de_semaine(tmp_path):
    j, _ = gel(tmp_path, [match(1, 1.4, 9)])
    r = S.bilan_bandes(j, ecrire=False)["regles"]["domicile"]
    assert r["geles"] == 1 and r["en_attente"] == 1 and r["cumule"]["matchs"] == 0 and r["cumule"]["taux"] is None


def test_le_journal_alpha_et_son_bilan_ne_changent_pas(tmp_path):
    j, _ = gel(tmp_path, [match(1, 1.4, 9)])
    assert S.bilan(j, ecrire=False)["pronostics_geles"] == 0                                   # les lignes « bande » ne sont pas des pronostics
    assert S.resultats(j, [dict(match(1, 1.4, 9), score_final={"buts_dom": 1, "buts_ext": 0})]) == 0
    assert S.geler(NUIT, j, [match(1, 1.4, 9)], params={}) == 0


def test_appel_reel_pipeline_et_archive(tmp_path):
    import inspect
    src = inspect.getsource(S.pipeline)
    assert "geler_bandes(matchs=matchs)" in src and "resultats_bandes(matchs=matchs)" in src and "bilan_bandes()" in src
    reels = S.charger_matchs()
    j = tmp_path / "reel.jsonl"
    S.geler_bandes(datetime(2026, 10, 1, tzinfo=timezone.utc), j, [m for m in reels if not m.get("score_final")][:300])
    assert all(l["bande"][0] <= l["cote"] <= l["bande"][1] for l in S._lire(j))
    b = S.bilan_bandes(j, ecrire=False)
    assert b["controles"]["doublons_match_regle"] == 0 and b["controles"]["gels_non_anterieurs_au_coup_d_envoi"] == 0
