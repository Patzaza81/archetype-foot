import json
from datetime import datetime, timezone

from matrice_scenarios import suivi_comportement as K
from tests.test_page_comportement import COTES, _match

MAINT = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


def _m(mid, ko, score=None):
    m = _match(COTES)
    m.update({"match_id": mid, "coup_d_envoi_utc": ko, "score_final": score})
    return m


def test_gele_un_match_futur(tmp_path):
    j = tmp_path / "j.jsonl"
    assert K.geler(MAINT, j, [_m("a", "2026-10-19T15:00:00Z")]) == 1
    l = json.loads(j.read_text().splitlines()[0])
    assert l["type"] == "pronostic" and l["selections"] and l["gele_le"] == "2026-10-19T12:00:00Z"


def test_ne_gele_jamais_un_match_commence(tmp_path):
    j = tmp_path / "j.jsonl"
    assert K.geler(MAINT, j, [_m("a", "2026-10-19T11:59:00Z"), _m("b", "2026-10-19T12:00:00Z")]) == 0
    assert not j.exists()


def test_ne_gele_pas_un_match_deja_joue(tmp_path):
    assert K.geler(MAINT, tmp_path / "j.jsonl", [_m("a", "2026-10-20T15:00:00Z", {"buts_dom": 1, "buts_ext": 0})]) == 0


def test_ne_regele_jamais(tmp_path):
    j = tmp_path / "j.jsonl"
    ms = [_m("a", "2026-10-19T15:00:00Z")]
    K.geler(MAINT, j, ms)
    avant = j.read_text()
    assert K.geler(datetime(2026, 10, 19, 13, 0, tzinfo=timezone.utc), j, ms) == 0
    assert j.read_text() == avant


def test_resultat_ajoute_sans_modifier_le_pronostic(tmp_path):
    j = tmp_path / "j.jsonl"
    K.geler(MAINT, j, [_m("a", "2026-10-19T15:00:00Z")])
    premiere = j.read_text().splitlines()[0]
    assert K.resultats(j, [_m("a", "2026-10-19T15:00:00Z", {"buts_dom": 3, "buts_ext": 0})]) == 1
    lignes = j.read_text().splitlines()
    assert lignes[0] == premiere and json.loads(lignes[1])["type"] == "resultat"
    assert K.resultats(j, [_m("a", "2026-10-19T15:00:00Z", {"buts_dom": 3, "buts_ext": 0})]) == 0


def test_resultat_ignore_pour_match_non_gele(tmp_path):
    assert K.resultats(tmp_path / "j.jsonl", [_m("zzz", "2026-10-19T15:00:00Z", {"buts_dom": 1, "buts_ext": 1})]) == 0


def test_bilan_ne_compte_que_les_matchs_geles_et_termines(tmp_path):
    j = tmp_path / "j.jsonl"
    K.geler(MAINT, j, [_m("a", "2026-10-19T15:00:00Z"), _m("b", "2026-10-19T16:00:00Z")])
    K.resultats(j, [_m("a", "2026-10-19T15:00:00Z", {"buts_dom": 3, "buts_ext": 0})])
    b = K.bilan(j, ecrire=False)
    assert b["pronostics_geles"] == 2 and b["matchs_termines"] == 1 and b["en_attente"] == 1
