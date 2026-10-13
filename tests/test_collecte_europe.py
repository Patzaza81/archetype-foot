import datetime
import pathlib

import pytest

import collecte_europe as ce

FIX = pathlib.Path(__file__).parent / "fixtures" / "pages_equipes"
AUJ = datetime.date(2026, 10, 13)


def page(nom):
    return (FIX / f"{nom}.html").read_text(encoding="utf-8")


def ligne(date, dom=True, gf=1, ga=0, adv="X", comp="ldc", saison="2026/2027"):
    return {"date": date, "domicile": dom, "buts_marques": gf, "buts_encaisses": ga, "adversaire": adv,
            "url_match": f"/live-score/{date}-{adv}.html", "source": "matchendirect", "competition": comp, "saison": saison}


# --- reconnaissance des compétitions (doivent PASSER) --------------------------------------------------------------------
@pytest.mark.parametrize("nom,code", [
    ("Europe : Ligue des Champions Phase de Ligue", "ldc"),
    ("Europe : Ligue Europa Phase de Ligue", "el"),
    ("Europe : Ligue Conférence Phase de Ligue", "ecl"),
    ("Europe : Ligue Conference Play-offs", "ecl"),
])
def test_competitions_europeennes_reconnues(nom, code):
    assert ce.competition_europeenne(nom) == code


# --- doivent ÉCHOUER (None) ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("nom", [
    "France : Ligue 1", None, "", "Europe : Ligue des Champions Féminine", "Europe : Ligue des Champions Jeunes",
    "Europe : Ligue Europa Qualifications", "Europe : Euro 2028", "Angleterre : Ligue des Champions",
])
def test_non_europeen_refuse(nom):
    assert ce.competition_europeenne(nom) is None


# --- lecture de page équipe (vraies pages) --------------------------------------------------------------------------------
def test_page_avec_europe_et_championnat():
    p = ce.lit_page_equipe(page("the_new_saints"), "The New Saints", date_reference=AUJ, saison="2026/2027")
    assert len(p["europe"]) == 3 and len(p["championnat"]) >= 3
    assert p["championnat_titre"] == "Cymru Premier"
    assert {m["competition"] for m in p["europe"]} <= {"ldc", "el", "ecl"}
    assert all(m["saison"] == "2026/2027" and m["date"] for m in p["europe"] + p["championnat"])


@pytest.mark.parametrize("nom", ["bradford", "cosenza"])
def test_club_sans_europe_a_zero_match_europeen(nom):
    p = ce.lit_page_equipe(page(nom), nom, date_reference=AUJ, saison="2026/2027")
    assert p["europe"] == [] and len(p["championnat"]) > 0


def test_championnat_introuvable_signale_et_pas_devine():
    p = ce.lit_page_equipe(page("aston_villa"), "Aston Villa", date_reference=AUJ, saison="2026/2027")
    assert p["championnat"] == [] and p["raison_championnat"] == "CHAMPIONNAT_INTROUVABLE"


# --- saison précédente ---------------------------------------------------------------------------------------------------
def test_saison_precedente_identique_est_ignoree():
    html = page("the_new_saints")
    r = ce.charge_club("https://x/equipe/tns.html", "The New Saints", fetch=lambda u: html, aujourdhui=AUJ)
    assert r["meta"]["saison_precedente"] == "ignoree_par_le_site"
    assert len(r["europe"]) == 3                                   # pas de doublon


def test_saison_precedente_differente_est_utilisee_avec_son_millesime(monkeypatch):
    appels = []

    def faux_lecteur(html, nom, date_reference=None, saison=None):
        if saison == "2026/2027":
            eu, ch = [ligne("2026-09-10")], [ligne("2026-09-12", comp="championnat")]
        else:
            assert date_reference == datetime.date(2026, 6, 30)       # « JJ/MM » lus avant la fin de saison
            eu = [ligne("2026-02-20", saison=saison)]
            ch = [ligne("2026-05-01", comp="championnat", saison=saison)]
        return {"europe": eu, "championnat": ch, "championnat_titre": "L", "europe_titres": [], "sans_date": 0, "raison_championnat": None}
    monkeypatch.setattr(ce, "lit_page_equipe", faux_lecteur)
    r = ce.charge_club("https://x/equipe/a.html", "A", fetch=lambda u: appels.append(u) or u, aujourdhui=AUJ)
    assert any("season=2025%2F2026" in u for u in appels)
    assert r["meta"]["saison_precedente"] == "utilisee"
    assert {m["saison"] for m in r["europe"]} == {"2026/2027", "2025/2026"}
    assert {m["saison"] for m in r["championnat"]} == {"2026/2027", "2025/2026"}


def test_saison_precedente_en_echec_ne_bloque_pas():
    def fetch(url):
        if "season=" in url:
            raise RuntimeError("403")
        return page("the_new_saints")
    r = ce.charge_club("https://x/equipe/tns.html", "The New Saints", fetch=fetch, aujourdhui=AUJ)
    assert r["meta"]["saison_precedente"].startswith("echec_fetch") and len(r["europe"]) == 3


# --- anti-fuite ----------------------------------------------------------------------------------------------------------
def test_avant_exclut_le_jour_du_match_et_apres():
    rows = [ligne("2026-10-01"), ligne("2026-10-13"), ligne("2026-10-20")]
    assert [m["date"] for m in ce.avant(rows, "2026-10-13")] == ["2026-10-01"]


# --- matchs à venir + entrée du moteur ------------------------------------------------------------------------------------
def test_matchs_a_venir_ignore_les_joues_et_les_non_europeens():
    enregs = [{"competition": "Europe : Ligue Europa Phase de Ligue", "score": None},
              {"competition": "Europe : Ligue Europa Phase de Ligue", "score": {"buts_dom": 2, "buts_ext": 1}},
              {"competition": "France : Ligue 1", "score": None}]
    assert len(ce.matchs_europeens_a_venir(enregs)) == 1


def test_archive_reelle_contient_des_matchs_europeens():
    e = ce.matchs_europeens_a_venir(ce.lit_archive("data/archive_test"))
    assert len(e) > 0 and all(ce.competition_europeenne(x["competition"]) for x in e)


def _enreg_avec_cotes():
    for e in ce.matchs_europeens_a_venir(ce.lit_archive("data/archive_test")):
        if e.get("cotes_betpawa"):
            return e
    pytest.skip("aucun match européen avec cotes dans l'archive")


def test_entree_evaluable_si_3_matchs_par_source_au_bon_lieu():
    e = _enreg_avec_cotes()
    d = e["date"]
    h = {"europe": [ligne("2026-09-01", True), ligne("2026-09-08", True), ligne("2026-09-15", True), ligne(d, True)],
         "championnat": [ligne("2026-09-02", True, comp=None)] * 3}
    a = {"europe": [ligne("2026-09-01", False)] * 3, "championnat": [ligne("2026-09-02", False, comp=None)] * 3}
    entree, n = ce.construit_entree_europe(e, h, a)
    assert n["evaluable"] and n["europe_dom_domicile"] == 3          # le match du jour est exclu
    assert entree["odds"]


def test_entree_non_evaluable_si_un_seul_lieu_manque():
    e = _enreg_avec_cotes()
    h = {"europe": [ligne("2026-09-01", False)] * 5, "championnat": [ligne("2026-09-02", True, comp=None)] * 3}
    a = {"europe": [ligne("2026-09-01", False)] * 3, "championnat": [ligne("2026-09-02", False, comp=None)] * 3}
    _, n = ce.construit_entree_europe(e, h, a)
    assert n["europe_dom_domicile"] == 0 and not n["evaluable"]


def test_execution_complete_hors_ligne(tmp_path):
    html = page("the_new_saints")
    b = ce.execution("data/archive_test", str(tmp_path / "s.json"), str(tmp_path / "c.json"), fetch=lambda u: html, pause=0, aujourdhui=AUJ)
    assert b["matchs"] == 50 and 0 <= b["evaluables"] <= 50
