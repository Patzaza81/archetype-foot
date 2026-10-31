"""Collecte ClubElo : validation du CSV (3 cas qui passent, 3 qui échouent), dates, reprise, arrêt après échecs consécutifs."""
import pytest

import collecte_clubelo as C

BON = "Rank,Club,Country,Level,Elo,From,To\nNone,Man City,ENG,1,2018.4,2026-10-20,2026-10-31\n1,Bayern,GER,1,2043.0,2026-10-25,2026-11-01\n"


@pytest.mark.parametrize("texte,n", [(BON, 2), (BON + "\n\n", 2), ("Rank,Club,Country,Level,Elo,From,To\nNone,Casa Pia,POR,1,1650.0,2026-10-01,2026-10-31", 1)])
def test_csv_valide(texte, n):
    assert len(C.valider(texte)) == n


@pytest.mark.parametrize("texte", ["", "<html>Not found</html>", "Rank,Club,Country,Level,Elo,From,To\n", "Rank,Club,Country,Level,Elo,From,To\n1,X,ENG,1,abc,2026-01-01,2026-01-02",
                                   "Rank,Club,Country,Level,Elo,From,To\n1,X,ENG,1", "Rank,Club,Country,Level,Elo,From,To\n1,,ENG,1,1500,2026-01-01,2026-01-02",
                                   "Rank,Club,Country,Level,Elo,From,To\n1,X,ENG,1,99999,2026-01-01,2026-01-02"])
def test_csv_refuse(texte):
    with pytest.raises(ValueError):
        C.valider(texte)


def test_dates():
    assert C.dates("2025-02-27", "2025-03-13", 7) == ["2025-02-27", "2025-03-06", "2025-03-13"]
    assert C.dates("2025-02-27", "2025-02-27", 7) == ["2025-02-27"] and C.dates("2025-03-01", "2025-02-27", 7) == []


class Reponse:
    def __init__(self, texte, code=200):
        self.text, self.code = texte, code

    def raise_for_status(self):
        if self.code >= 400:
            raise RuntimeError(f"HTTP {self.code}")


class Session:
    def __init__(self, reponses):
        self.reponses, self.appels = reponses, []

    def get(self, url, **kw):
        self.appels.append(url)
        return self.reponses.pop(0)


def test_collecte_ecrit_reprend_et_ne_retelecharge_pas(tmp_path):
    s = Session([Reponse(BON), Reponse(BON)])
    m = C.collecter(["2025-02-27", "2025-03-06"], tmp_path, s, 0, dormir=lambda x: None, log=lambda *a: None)
    assert m["ok"] == ["2025-02-27", "2025-03-06"] and (tmp_path / "2025-02-27.csv").read_text().startswith(C.ENTETE)
    s2 = Session([Reponse(BON)])
    m2 = C.collecter(["2025-02-27", "2025-03-06", "2025-03-13"], tmp_path, s2, 0, dormir=lambda x: None, log=lambda *a: None)
    assert m2["deja"] == ["2025-02-27", "2025-03-06"] and m2["ok"] == ["2025-03-13"] and len(s2.appels) == 1


def test_arret_apres_trois_echecs_de_suite_et_reponse_refusee_non_ecrite(tmp_path):
    mauvaises = [Reponse("<html>erreur</html>"), Reponse("", 503), Reponse(BON.replace("2018.4", "x"))] * 2     # chaque date essaie http puis https
    s = Session(mauvaises + [Reponse(BON)])
    m = C.collecter(["a", "b", "c", "d"], tmp_path, s, 0, dormir=lambda x: None, log=lambda *a: None)
    assert m["arret"] and len(m["erreurs"]) == 3 and not list(tmp_path.glob("*.csv")) and len(s.appels) == 6


def test_repli_https_si_http_echoue_et_ordre_des_adresses(tmp_path):
    s = Session([Reponse("", 500), Reponse(BON)])
    m = C.collecter(["2025-02-27"], tmp_path, s, 0, dormir=lambda x: None, log=lambda *a: None)
    assert m["ok"] == ["2025-02-27"] and s.appels[0].startswith("http://") and s.appels[1].startswith("https://")
    s2 = Session([Reponse(BON)])
    C.collecter(["2025-03-06"], tmp_path, s2, 0, dormir=lambda x: None, log=lambda *a: None)
    assert len(s2.appels) == 1                                              # http répond : pas d'appel https


def test_un_echec_isole_ne_stoppe_pas(tmp_path):
    s = Session([Reponse(BON), Reponse("", 500), Reponse("", 500), Reponse(BON)])
    m = C.collecter(["2025-02-27", "2025-03-06", "2025-03-13"], tmp_path, s, 0, dormir=lambda x: None, log=lambda *a: None)
    assert not m["arret"] and m["ok"] == ["2025-02-27", "2025-03-13"] and list(m["erreurs"]) == ["2025-03-06"]
