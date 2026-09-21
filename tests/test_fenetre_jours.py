"""Option PRECALCUL_JOURS (21/09/2026) : run limité à aujourd'hui + demain, sans jamais réduire le run planifié par erreur."""
import datetime
import json

import pytest

import precalcul


@pytest.mark.parametrize("valeur", ["2", " 2 ", "2\n"])
def test_deux_jours_seulement_pour_la_valeur_2(monkeypatch, valeur):
    monkeypatch.setenv("PRECALCUL_JOURS", valeur)
    assert precalcul.jours_fenetre() == 2


@pytest.mark.parametrize("valeur", ["4", "", "3", "02", "deux", "1", "22", "0"])
def test_toute_autre_valeur_garde_la_fenetre_complete(monkeypatch, valeur):
    monkeypatch.setenv("PRECALCUL_JOURS", valeur)
    assert precalcul.jours_fenetre() == 4


def test_variable_absente_garde_la_fenetre_complete(monkeypatch):
    monkeypatch.delenv("PRECALCUL_JOURS", raising=False)
    assert precalcul.jours_fenetre() == 4


def _prepare(tmp_path, monkeypatch, jours):
    monkeypatch.chdir(tmp_path)
    if jours is None:
        monkeypatch.delenv("PRECALCUL_JOURS", raising=False)
    else:
        monkeypatch.setenv("PRECALCUL_JOURS", jours)
    monkeypatch.setattr(precalcul, "dates_j2_j3", lambda aujourdhui=None: {"2026-09-23", "2026-09-24"})
    m = lambda mid, d: {"match_id": mid, "date": d, "domicile": "A" + mid, "exterieur": "B" + mid, "competition": "France : Ligue 1", "heure": "20:00"}
    json.dump([m("j0", "2026-09-21")], open(precalcul.FICHIER_MATCHS_DU_JOUR, "w"))
    json.dump([m("j1", "2026-09-22")], open(precalcul.FICHIER_MATCHS_DEMAIN, "w"))
    json.dump([m("j2", "2026-09-23"), m("j3", "2026-09-24"), m("hors", "2026-09-30")], open(precalcul.FICHIER_MATCHS_SEMAINE, "w"))


def _ids(res):
    return sorted(x["match_id"] for x in res[0])


def test_run_complet_j0_a_j3(tmp_path, monkeypatch):
    _prepare(tmp_path, monkeypatch, None)
    assert _ids(precalcul.charge_matchs_fenetre()) == ["j0", "j1", "j2", "j3"]


def test_run_a_deux_jours_ignore_matchs_semaine_meme_present(tmp_path, monkeypatch):
    _prepare(tmp_path, monkeypatch, "2")
    res = precalcul.charge_matchs_fenetre()
    assert _ids(res) == ["j0", "j1"] and res[3] == 0            # nb_j2_j3 = 0


def test_une_valeur_invalide_ne_reduit_pas_le_run(tmp_path, monkeypatch):
    _prepare(tmp_path, monkeypatch, "3")
    assert _ids(precalcul.charge_matchs_fenetre()) == ["j0", "j1", "j2", "j3"]


def test_la_purge_betpawa_garde_j2_j3_meme_en_run_a_deux_jours():
    import inspect
    src = inspect.getsource(precalcul.main)
    assert "purge_betpawa_matchs_joues(dates_fenetre | set(dates_j2_j3()))" in src


def test_le_workflow_expose_l_option_et_saute_la_liste_j2_j3():
    import yaml
    d = yaml.safe_load(open("/home/claude/archetype-foot/.github/workflows/pipeline.yml", encoding="utf-8"))
    inputs = d[True]["workflow_dispatch"]["inputs"]
    assert inputs["jours"]["default"] == "4" and inputs["jours"]["options"] == ["4", "2"]
    steps = d["jobs"]["run-pipeline"]["steps"]
    semaine = next(s for s in steps if "J+2 à J+3" in s.get("name", ""))
    assert semaine["if"] == "github.event.inputs.jours != '2'"
    pre = next(s for s in steps if s.get("id") == "precalcul")
    assert pre["env"]["PRECALCUL_JOURS"] == "${{ github.event.inputs.jours }}"
