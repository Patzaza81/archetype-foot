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


# --- AJOUT 28/09/2026 : données V3 au format de la page « Sélections Archetype » (archetype_v3.js) ------------------

@pytest.mark.parametrize("v3,site", [("1x2_1", "1x2_domicile"), ("dc_X2", "double_chance_X2"),
                                     ("over_2_5", "over_under_total_2.5_over"), ("under_3_5", "over_under_total_3.5_under"),
                                     ("btts_yes", "btts_oui"), ("home_over_0_5", "buts_equipe_domicile_0.5_over")])
def test_noms_de_marches_lus_par_le_site(v3, site):
    assert mp.V3_VERS_SITE[v3] == site


@pytest.mark.parametrize("v3", ["1x2_2", "under_2_5", "away_under_1_5"])
def test_aucun_nom_v3_brut_ne_part_vers_le_site(v3):
    assert mp.V3_VERS_SITE[v3] != v3


def _selection(marche="over_2_5"):
    return {"marche": marche, "libelle": "x", "cote": 1.6, "probabilite": 0.72, "edge": 0.095, "edv": 15.2,
            "justification": "j", "raisons_saison": ["✓ A marque", "✓ B encaisse"], "raisons_recent": ["✓ 5 / 6"]}


def test_candidat_au_format_de_la_page_archetype():
    c = mp.candidat_site(_selection(), "P1", 6)
    assert c["marche"] == "over_under_total_2.5_over" and abs(c["edv"] - 0.152) < 1e-12 and c["niveau"] == "V3_ECHANTILLON_UTILISABLE"
    j = c["justification"]
    assert j["donnees_suffisantes"] and j["resume"].startswith("Probabilité calibrée 72 % contre 62 % selon la cote")
    assert j["resume"] not in [p["texte"] for p in j["preuves"]]          # la synthèse ne recopie aucune preuve
    assert [p["type"] for p in j["preuves"]] == ["v3_controle_saison", "v3_forme_recente", "ev_percentage"]
    assert c["points_de_vigilance"] == [mp.VIGILANCE_V3]


@pytest.mark.parametrize("n_min,nb", [(3, 2), (4, 2), (5, 1)])
def test_vigilance_petit_echantillon(n_min, nb):
    assert len(mp.candidat_site(_selection(), "P1", n_min)["points_de_vigilance"]) == nb


def test_signal_seul_bloc_moteur_v3_jamais_la_v2():
    x = {"match_id": "m", "date": "2026-09-28", "heure": "19:00", "competition": "C", "domicile": "A",
         "exterieur": "B", "statut": "EVALUE", "n_dom": 6, "n_ext": 6,
         "selections": [_selection("over_2_5"), _selection("1x2_1")]}
    s = mp.signal_site(x)
    assert s["moteur_utilise"] == "moteur_v3" and "moteur_v2_6_9" not in s and "shrink_v1" not in s
    assert set(s["moteur_v3"]["selection"]) == {"P1", "P2"} and s["moteur_v3"]["statut"] == "OK"
    assert mp.signal_site({**x, "selections": []})["moteur_v3"]["selection"] == {}


def test_execution_ecrit_les_signaux(tmp_path):
    d, sortie = str(tmp_path / "archive"), str(tmp_path / "v3" / "pronostics_v3.json")
    _ecrit(d, [_enreg("ok")])
    mp.execution(dossier=d, fichier_sortie=sortie, maintenant=MAINTENANT)
    with open(sortie, encoding="utf-8") as f:
        out = json.load(f)
    assert [s["match_id"] for s in out["signaux"]] == ["ok"] and out["signaux"][0]["moteur_utilise"] == "moteur_v3"


def test_page_v3_copie_de_la_page_archetype():
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(racine, "archetype_v3.js"), encoding="utf-8") as f:
        js = f.read()
    with open(os.path.join(racine, "pronostics_v3.html"), encoding="utf-8") as f:
        html = f.read()
    assert 'const CLE_MOTEUR = "moteur_v3"' in js and "data/v3/pronostics_v3.json" in js
    assert "precalcul_leger.json" not in js.split("fetch(")[-1]          # jamais les données V2
    assert "archetype_v3.js" in html and "archetype.css" in html and "expérimental" in html


@pytest.mark.parametrize("n,niveau", [(3, "V3_ECHANTILLON_FAIBLE"), (4, "V3_ECHANTILLON_FAIBLE"),
                                      (5, "V3_ECHANTILLON_UTILISABLE"), (7, "V3_ECHANTILLON_UTILISABLE"),
                                      (8, "V3_ECHANTILLON_SOLIDE"), (12, "V3_ECHANTILLON_TRES_SOLIDE")])
def test_fiabilite_affichee_selon_l_echantillon(n, niveau):
    assert mp.niveau_echantillon(n) == niveau


def test_page_v3_sans_roles_de_la_v2():
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(racine, "archetype_v3.js"), encoding="utf-8") as f:
        js = f.read()
    code = "\n".join(l for l in js.splitlines() if not l.lstrip().startswith("//"))
    for role in ("Favori du Modèle", "Value Bet", "Coup de Poker", "Confrontations directes"):
        assert role not in code
    for niveau in ("V3_ECHANTILLON_FAIBLE", "V3_ECHANTILLON_UTILISABLE", "V3_ECHANTILLON_SOLIDE", "V3_ECHANTILLON_TRES_SOLIDE"):
        assert niveau in code


@pytest.mark.parametrize("lambdas,attendu", [((1.62, 1.1), "buts attendus par la V3 : 1,62 – 1,10"),
                                             ((2.0, 0.85), "buts attendus par la V3 : 2,00 – 0,85"),
                                             ((0.9, 1.4), "buts attendus par la V3 : 0,90 – 1,40")])
def test_synthese_avec_les_buts_attendus_de_la_v3(lambdas, attendu):
    assert attendu in mp.synthese(_selection(), lambdas)


@pytest.mark.parametrize("lambdas", [None, (None, 1.2), (1.2, None)])
def test_synthese_sans_buts_attendus_inconnus(lambdas):
    assert "buts attendus" not in mp.synthese(_selection(), lambdas)
