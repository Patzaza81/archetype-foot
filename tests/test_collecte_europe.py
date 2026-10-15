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
    # Le nombre de matchs européens à venir de l'archive réelle change chaque jour (50 en 'dur' faisait échouer le pipeline
    # dès qu'il y en avait moins) : on compare à ce que contient l'archive.
    attendus = len(ce.matchs_europeens(ce.lit_archive("data/archive_test"), False))
    assert attendus > 0 and b["matchs"] == attendus and 0 <= b["evaluables"] <= attendus


# --- liens d'équipes fournis à la main ------------------------------------------------------------------------------------
URL = "https://www.matchendirect.fr/equipe/man-city_abc.html"


def test_lien_manuel_utilise_quand_l_archive_n_a_pas_de_lien():
    assert ce.lien_equipe({"url_equipe": None}, "Man City", {"Man City": URL}) == URL
    assert ce.lien_equipe({}, " Man City ", {"Man City": URL}) == URL
    assert ce.lien_equipe(None, "Man City", {"Man City": URL}) == URL


def test_lien_de_l_archive_garde_la_priorite():
    assert ce.lien_equipe({"url_equipe": "https://x/archive"}, "Man City", {"Man City": URL}) == "https://x/archive"


def test_lien_absent_ou_nom_inconnu_donne_none():
    assert ce.lien_equipe({}, "PSG", {"Man City": URL}) is None
    assert ce.lien_equipe({}, None, {"Man City": URL}) is None
    assert ce.lien_equipe({}, "PSG", {}) is None


def test_fichier_de_liens_refuse_les_urls_invalides(tmp_path):
    import json
    f = tmp_path / "l.json"
    f.write_text(json.dumps({"_aide": "texte", "Man City": URL, "PSG": "", "Hearts": "https://autre-site.com/hearts",
                             "Brann": "http://www.matchendirect.fr/equipe/brann.html", "Dortmund": "n'importe quoi"}))
    assert ce.lit_liens(str(f)) == {"Man City": URL}
    assert ce.lit_liens(str(tmp_path / "absent.json")) == {}


def test_execution_charge_le_club_dont_le_lien_vient_du_fichier(tmp_path, monkeypatch):
    import copy

    # Le test doit fournir des liens manuels aux équipes réellement présentes dans
    # l'archive de test, sans dépendre de son contenu évolutif.
    e = copy.deepcopy(_enreg_avec_cotes())
    e["equipe_dom"] = dict(e.get("equipe_dom") or {})
    e["equipe_ext"] = dict(e.get("equipe_ext") or {})
    e["equipe_dom"].pop("url_equipe", None)
    e["equipe_ext"].pop("url_equipe", None)
    monkeypatch.setattr(ce, "lit_archive", lambda dossier: [e])

    url_dom = URL
    url_ext = "https://www.matchendirect.fr/equipe/psg_x.html"
    vus = []
    ce.execution("data/archive_test", str(tmp_path / "s.json"), str(tmp_path / "c.json"),
                 fetch=lambda u: vus.append(u) or page("the_new_saints"), pause=0, aujourdhui=AUJ,
                 liens={e["domicile"]: url_dom, e["exterieur"]: url_ext})
    assert url_dom in vus and url_ext in vus


def test_diagnostic_rubriques_nationales_dans_meta():
    r = ce.charge_club("https://x/e.html", "The New Saints", fetch=lambda u: page("the_new_saints"), aujourdhui=AUJ)
    assert "Cymru Premier" in r["meta"]["rubriques_avec_matchs"] and r["meta"]["rubriques_nationales"]


# --- complément Livescore dans la collecte --------------------------------------------------------------------------------
def _mini_archive(tmp_path, n=3):
    import gzip
    import json
    d = tmp_path / "arch"
    d.mkdir()
    enregs = ce.matchs_europeens_a_venir(ce.lit_archive("data/archive_test"))[:n]
    with gzip.open(d / "2026-10-15.json.gz", "wt", encoding="utf-8") as f:
        json.dump({e["match_id"]: e for e in enregs}, f)
    return str(d)


def _index_ls(tmp_path, matchs):
    import json
    import source_livescore as sl
    d = tmp_path / "ls"
    d.mkdir()
    (d / "2026-10-01.json").write_text(json.dumps(matchs))
    return sl.charge_index(str(d))


def test_livescore_complete_un_club_sans_lien_matchendirect(tmp_path):
    def mm(date, dom, ext, a, b):
        return {"date": date, "pays": "Latvia", "stage": "Virsliga", "dom": dom, "ext": ext, "buts_dom": a, "buts_ext": b}
    idx = _index_ls(tmp_path, [mm("2026-09-01", "Riga FC", "A", 1, 0), mm("2026-09-08", "Riga FC", "B", 2, 2), mm("2026-09-15", "Riga FC", "C", 0, 1)])
    import json
    b = ce.execution(_mini_archive(tmp_path), str(tmp_path / "s.json"), str(tmp_path / "c.json"), fetch=lambda u: page("the_new_saints"),
                     pause=0, aujourdhui=AUJ, liens={}, livescore=idx, alias={})
    assert b["livescore"]["actif"] and isinstance(b["livescore"]["equipes_non_appariees"], dict)
    assert len(b["livescore"]["equipes_non_appariees"]) > 0               # les autres clubs de l'archive ne sont pas dans cet index


def test_livescore_absent_ne_change_rien(tmp_path):
    b = ce.execution(_mini_archive(tmp_path), str(tmp_path / "s.json"), str(tmp_path / "c.json"), fetch=lambda u: page("the_new_saints"),
                     pause=0, aujourdhui=AUJ, liens={}, livescore={}, alias={})
    assert b["livescore"] == {"actif": False, "equipes_non_appariees": {}}


def test_le_cache_matchendirect_n_est_pas_pollue_par_livescore(tmp_path):
    import json
    idx = _index_ls(tmp_path, [{"date": "2026-09-01", "pays": "Wales", "stage": "Cymru Premier", "dom": "The New Saints", "ext": "Z", "buts_dom": 5, "buts_ext": 0}])
    c = tmp_path / "c.json"
    ce.execution(_mini_archive(tmp_path), str(tmp_path / "s.json"), str(c), fetch=lambda u: page("the_new_saints"), pause=0, aujourdhui=AUJ,
                 liens={}, livescore=idx, alias={})
    assert all(m.get("source") != "livescore" for v in json.loads(c.read_text()).values() for g in ("europe", "championnat") for m in v["donnees"][g])
