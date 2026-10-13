import datetime
import json
import pathlib

import pytest

import source_livescore as sl

FIX = pathlib.Path(__file__).parent / "fixtures" / "livescore_2026-10-13.json"


def payload():
    return json.loads(FIX.read_text(encoding="utf-8"))


def ligne(date, dom=True, gf=1, ga=0, adv="X", pays="Latvia", stage="Virsliga"):
    return {"date": date, "domicile": dom, "buts_marques": gf, "buts_encaisses": ga, "adversaire": adv, "url_match": None,
            "source": "livescore", "pays": pays, "stage": stage}


def index_de(tmp_path, matchs):
    d = tmp_path / "ls"
    d.mkdir()
    (d / "2026-10-01.json").write_text(json.dumps(matchs))
    return sl.charge_index(str(d))


def m(date, dom, ext, gd, ge, pays="Latvia", stage="Virsliga"):
    return {"date": date, "pays": pays, "stage": stage, "dom": dom, "ext": ext, "buts_dom": gd, "buts_ext": ge}


# --- lecture du flux (vraie réponse du 13/10) ---------------------------------------------------------------------------------
def test_seuls_les_matchs_termines_sont_gardes():
    out = sl.compacte(payload())
    assert len(out) == 12 and all(isinstance(x["buts_dom"], int) and isinstance(x["buts_ext"], int) for x in out)
    assert not any(x["dom"] == "Lens" for x in out)          # Lens - Sporting CP : pas encore joué (NS)


def test_evenement_incomplet_ecarte():
    p = {"Stages": [{"Cnm": "X", "Snm": "Y", "Events": [{"Eps": "FT", "Tr1": "1", "T1": [{"Nm": "A"}], "T2": [{"Nm": "B"}], "Esd": 20261013100000},
                                                       {"Eps": "FT", "Tr1": "a", "Tr2": "1", "T1": [{"Nm": "A"}], "T2": [{"Nm": "B"}], "Esd": 20261013100000},
                                                       {"Eps": "AET", "Tr1": "2", "Tr2": "1", "T1": [{"Nm": "A"}], "T2": [{"Nm": "B"}], "Esd": 20261013100000}]}]}
    assert sl.compacte(p) == []


@pytest.mark.parametrize("pays,stage,code", [("Champions League", "League Stage", "ldc"), ("Europa League", "League Stage", "el"),
                                               ("Conference League", "Knockout Phase Play-offs", "ecl")])
def test_competition_europe_reconnue(pays, stage, code):
    assert sl.competition_europe(pays, stage) == code


@pytest.mark.parametrize("pays,stage", [("Champions League", "Qualification Round 2"), ("UEFA Youth League", "Champions League Path"),
                                          ("Asia", "AFC Champions League Elite: East"), ("England", "Premier League"), (None, None)])
def test_competition_europe_refusee(pays, stage):
    assert sl.competition_europe(pays, stage) is None


@pytest.mark.parametrize("pays,stage", [("Brazil", "Serie A"), ("Latvia", "Virsliga"), ("Turkiye", "1st Lig")])
def test_championnat_reconnu(pays, stage):
    assert sl.est_championnat(pays, stage)


@pytest.mark.parametrize("pays,stage", [("Brazil", "Copa do Brasil"), ("Scotland", "Challenge Cup"), ("Women's Euro U17", "Qualification Round 1"),
                                          ("International Friendlies", "Women's Friendlies"), ("Asia", "AFC Champions League Elite: West"),
                                          ("Champions League", "League Stage")])
def test_championnat_refuse(pays, stage):
    assert not sl.est_championnat(pays, stage)


# --- rapprochement des noms ---------------------------------------------------------------------------------------------------
def test_apparie_nom_identique_ou_alias(tmp_path):
    idx = index_de(tmp_path, [m("2026-10-01", "Riga FC", "Valmiera", 2, 1)])
    assert sl.apparie("Riga FC", idx) == sl.norm("Riga FC")
    assert sl.apparie("Riga", idx, {"Riga": ["Riga FC"]}) == sl.norm("Riga FC")
    assert sl.apparie("FC Riga", idx) == sl.apparie("Riga FC", idx)      # « FC » ne compte pas


def test_non_apparie_jamais_devine(tmp_path):
    idx = index_de(tmp_path, [m("2026-10-01", "Riga FC", "Valmiera", 2, 1)])
    assert sl.apparie("Riga United", idx) is None
    assert sl.apparie("Valmieras", idx) is None
    assert sl.apparie(None, idx) is None
    assert sl.apparie("Dinamo Riga", idx, {"Dinamo Riga": ["Nom inexistant"]}) is None


# --- complément de l'historique -----------------------------------------------------------------------------------------------
def test_complete_ajoute_les_matchs_absents_et_ne_double_jamais(tmp_path):
    idx = index_de(tmp_path, [m("2026-09-20", "Riga FC", "A", 2, 0), m("2026-09-27", "B", "Riga FC", 1, 1),
                              m("2026-10-01", "Riga FC", "C", 3, 1), m("2026-10-08", "Riga FC", "D", 0, 0)])
    # Matchendirect a déjà le match du 2026-09-27, daté 28/09 (décalage d'un jour) : pas de doublon
    donnees = {"europe": [], "championnat": [ligne("2026-09-28", False, 1, 1, "B")], "meta": {}}
    out, info = sl.complete(donnees, "Riga FC", idx)
    assert info["statut"] == "OK" and info["ajouts"]["championnat"] == 3
    assert [x["date"] for x in out["championnat"]] == ["2026-09-20", "2026-09-28", "2026-10-01", "2026-10-08"]


def test_complete_ne_modifie_pas_les_lignes_existantes(tmp_path):
    idx = index_de(tmp_path, [m("2026-10-01", "Riga FC", "C", 3, 1)])
    ex = ligne("2026-10-01", True, 9, 9, "C")
    out, _ = sl.complete({"europe": [], "championnat": [ex], "meta": {}}, "Riga FC", idx)
    assert out["championnat"] == [ex]


def test_complete_club_non_apparie_laisse_les_donnees_et_suggere(tmp_path):
    idx = index_de(tmp_path, [m("2026-10-01", "Kairat Almaty", "C", 3, 1, "Kazakhstan", "Premier League")])
    donnees = {"europe": [], "championnat": [], "meta": {}}
    out, info = sl.complete(donnees, "K. Almaty", idx)
    assert info["statut"] == "NON_APPARIE" and out["championnat"] == []


def test_championnat_ambigu_donne_zero_donnee(tmp_path):
    idx = index_de(tmp_path, [m("2026-10-01", "Riga FC", "A", 1, 0, "Latvia", "Virsliga"), m("2026-10-05", "Riga FC", "B", 1, 0, "Latvia", "Other League")])
    assert sl.historique_club(sl.norm("Riga FC"), idx)["championnat"] == []


def test_europe_des_deux_cotes_et_qualifications_exclues(tmp_path):
    idx = index_de(tmp_path, [m("2026-09-17", "Lens", "Sporting CP", 2, 1, "Champions League", "League Stage"),
                              m("2026-08-20", "Lens", "Y", 1, 0, "Champions League", "Qualification Round 3"),
                              m("2026-10-01", "Z", "Lens", 0, 2, "Champions League", "League Stage")])
    h = sl.historique_club(sl.norm("Lens"), idx)
    assert [x["date"] for x in h["europe"]] == ["2026-09-17", "2026-10-01"] and all(x["competition"] == "ldc" for x in h["europe"])


# --- téléchargement ----------------------------------------------------------------------------------------------------------
class Rep:
    def __init__(self, code, data): self.status_code, self._d = code, data
    def json(self): return self._d


def test_mise_a_jour_telecharge_les_jours_absents_et_ne_refait_pas_les_presents(tmp_path):
    appels = []

    def get(u):
        appels.append(u)
        return Rep(200, payload())
    d = str(tmp_path / "ls")
    b1 = sl.met_a_jour(3, aujourdhui=datetime.date(2026, 10, 13), dossier=d, get=get, pause=0)
    b2 = sl.met_a_jour(3, aujourdhui=datetime.date(2026, 10, 13), dossier=d, get=get, pause=0)
    assert b1["telecharges"] == 3 and b2["telecharges"] == 0 and b2["deja_presents"] == 3 and len(appels) == 3
    assert "20261010" in appels[0] and "20261012" in appels[2]            # jamais aujourd'hui


def test_echec_http_note_et_ne_bloque_pas(tmp_path, monkeypatch):
    monkeypatch.setattr(sl.time, "sleep", lambda s: None)
    b = sl.met_a_jour(2, aujourdhui=datetime.date(2026, 10, 13), dossier=str(tmp_path / "ls"), get=lambda u: Rep(403, {}), pause=0)
    assert b["telecharges"] == 0 and len(b["echecs"]) == 2
