"""Branchement V3 en parallèle (moteur_v3_pipeline.py) : 3 cas qui passent / 3 qui échouent par règle."""
import datetime
import gzip
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import moteur_v3_pipeline as mp  # noqa: E402

MAINTENANT = datetime.datetime(2026, 9, 27, 12, 0, tzinfo=datetime.timezone.utc)


def _matchs(domicile, n, bm=2, be=1, debut=1):
    return [{"date": f"2026-08-{debut + i:02d}", "domicile": domicile, "adversaire": f"X{i}",
             "buts_marques": bm if i % 2 == 0 else bm - 1, "buts_encaisses": be if i % 3 else 0}
            for i in range(n)]


def _enreg(mid, date="2026-09-28", ko="2026-09-28T18:00:00Z", score=None, n=8):
    return {"match_id": mid, "date": date, "coup_d_envoi_utc": ko, "heure_cameroun": "19:00",
            "competition": "Italie : Série B", "domicile": "A", "exterieur": "B", "testable": True,
            "score": {"buts_dom": score[0], "buts_ext": score[1]} if score else None,
            "cotes_betpawa": {"1x2": {"1": 1.9, "N": 3.4, "2": 4.0}, "btts": {"Oui": 1.8, "Non": 1.95},
                              "over_under_2.5": {"plus": 1.9, "moins": 1.9},
                              "cages_inviolees_domicile": {"oui": 3.0, "non": 1.35}},
            "cotes_observees": {"Double chance - 1X": 1.3},
            "equipe_dom": {"matchs": _matchs(True, n) + _matchs(False, n, debut=15)},
            "equipe_ext": {"matchs": _matchs(False, n, bm=1, be=2) + _matchs(True, n, bm=1, be=2, debut=15)}}


def _ecrit(dossier, enregs):
    os.makedirs(dossier, exist_ok=True)
    par_date = {}
    for e in enregs:
        par_date.setdefault(e["date"], {})[e["match_id"]] = e
    for d, contenu in par_date.items():
        with gzip.open(os.path.join(dossier, f"{d}.json.gz"), "wt", encoding="utf-8") as f:
            json.dump(contenu, f)


@pytest.mark.parametrize("marche,attendu", [("1x2_1", "Victoire domicile"), ("over_2_5", "Plus de 2,5 buts"),
                                            ("home_under_1_5", "Domicile marque moins de 1,5 but")])
def test_libelles(marche, attendu):
    assert mp.libelle(marche) == attendu


@pytest.mark.parametrize("a,b", [("1x2_1", "dc_X2"), ("over_2_5", "exact_goals_3"), ("home_over_0_5", "clean_away")])
def test_meme_exposition(a, b):
    assert mp.groupe_exposition(a) == mp.groupe_exposition(b)


@pytest.mark.parametrize("a,b", [("1x2_1", "over_2_5"), ("btts_yes", "under_2_5"), ("home_over_0_5", "away_over_0_5")])
def test_expositions_differentes(a, b):
    assert mp.groupe_exposition(a) != mp.groupe_exposition(b)


def test_cotes_converties_sans_invention():
    c = mp.cotes_v3(_enreg("m"))
    assert c["1x2_1"] == 1.9 and c["btts_yes"] == 1.8 and c["dc_1X"] == 1.3 and c["clean_home"] == 3.0
    assert not any(k.endswith("_non") for k in c)                   # complément de cage : aucun équivalent V3


def test_competition_jamais_transmise_au_moteur():
    assert set(mp.entree_v3(_enreg("m"))) == {"home_matches", "away_matches", "odds"}


@pytest.mark.parametrize("e", [_enreg("a"), _enreg("b", date="2026-09-27", ko="2026-09-27T20:00:00Z"),
                               _enreg("c", date="2026-09-30", ko=None)])
def test_match_a_venir(e):
    assert mp.a_venir(e, MAINTENANT) is True


@pytest.mark.parametrize("e", [_enreg("a", score=(1, 0)), _enreg("b", date="2026-09-27", ko="2026-09-27T10:00:00Z"),
                               _enreg("c", date="2026-09-26", ko=None)])
def test_match_passe_ou_joue(e):
    assert mp.a_venir(e, MAINTENANT) is False


def test_calibration_seulement_sur_matchs_joues_avant_aujourdhui():
    joues = [_enreg(f"j{i}", date="2026-09-20", score=(i % 3, 1)) for i in range(300)]
    exclus = [_enreg("jour", date="2026-09-27", score=(2, 0)), _enreg("futur", score=(1, 1)), _enreg("sans_score",
                                                                                                       date="2026-09-20")]
    cal, n = mp.entraine_calibration(joues + exclus, "2026-09-27")
    assert n == 300 and cal.fit_result.ready
    cal2, n2 = mp.entraine_calibration(exclus, "2026-09-27")
    assert n2 == 0 and not cal2.fit_result.ready


def test_double_controle_obligatoire_et_justification():
    p = mp.preuves(_enreg("m"), ["1x2_1", "btts_yes", "clean_home", "exact_goals_2"])
    assert "double_controle_raisons" in p["1x2_1"] and "double_controle_raisons" in p["btts_yes"]
    assert p["clean_home"]["double_control_ok"] is False and p["clean_home"]["justification"] is None
    for bloc in p.values():
        assert bool(bloc["justification"]) == bloc["double_control_ok"]


def test_execution_ecrit_le_fichier_et_ne_plante_jamais(tmp_path):
    d, sortie = str(tmp_path / "archive"), str(tmp_path / "v3" / "pronostics_v3.json")
    vide = _enreg("sans_matchs")
    vide["equipe_dom"] = {"matchs": []}
    sans_cote = _enreg("sans_cote")
    sans_cote["cotes_betpawa"], sans_cote["cotes_observees"] = {}, {}
    _ecrit(d, [_enreg("ok"), vide, sans_cote, _enreg("joue", date="2026-09-20", score=(2, 1))])
    bilan = mp.execution(dossier=d, fichier_sortie=sortie, maintenant=MAINTENANT)
    with open(sortie, encoding="utf-8") as f:
        out = json.load(f)
    assert out["statut"] == mp.STATUT and bilan["matchs"] == 3
    statuts = {m["match_id"]: m["statut"] for m in out["matchs"]}
    assert statuts["ok"] == "EVALUE" and statuts["sans_cote"] == "SANS_COTE"
    assert statuts["sans_matchs"].startswith("NON_EVALUE")
    assert out["calibration"]["prete"] is False                      # 1 seul match joué : pas de calibration
    assert bilan["selections"] == 0 and "CALIBRATION_ABSENTE" in bilan["raisons_de_rejet"]
