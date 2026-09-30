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
    assert set(mp.entree_v3(_enreg("m"))) == {"home_matches", "away_matches", "odds", "handicap_lines"}


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
    assert s["moteur_utilise"] == "moteur_v3" and "moteur_v2_6_9" not in s
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


@pytest.mark.parametrize("n,attendu", [(3, "Probabilité calibrée 72 % contre 62 % selon la cote 1,60 · marge +15,2 % · 3 matchs au même lieu."),
                                       (6, "· 6 matchs au même lieu."), (12, "· 12 matchs au même lieu.")])
def test_resume_standard_une_ligne(n, attendu):
    assert attendu in mp.synthese(_selection(), n)


@pytest.mark.parametrize("n", [None, 3, 12])
def test_resume_sans_buts_attendus_ni_preuve(n):
    t = mp.synthese(_selection(), n)
    assert "buts attendus" not in t and "double contrôle" not in t and t.count(".") >= 1


# --- AJOUT 28/09/2026 : aperçu NON calibré tant que la calibration n'est pas prête (décision de Patrick) -------------

def _x(selections=(), apercu=()):
    return {"match_id": "m", "date": "2026-09-28", "heure": "19:00", "competition": "C", "domicile": "A",
            "exterieur": "B", "statut": "EVALUE", "n_dom": 6, "n_ext": 6, "lambda_dom": 1.5, "lambda_ext": 0.9,
            "selections": list(selections), "apercu_non_calibre": list(apercu)}


@pytest.mark.parametrize("apercu", [[_selection()], [_selection(), _selection("1x2_1")],
                                    [_selection("dc_1X"), _selection("btts_yes"), _selection("home_over_0_5")]])
def test_apercu_affiche_et_marque_non_calibre(apercu):
    s = mp.signal_site(_x(apercu=apercu))["moteur_v3"]
    assert s["apercu_non_calibre"] is True and len(s["selection"]) == len(apercu)
    for c in s["selection"].values():
        assert c["apercu_non_calibre"] is True and c["points_de_vigilance"][0] == mp.VIGILANCE_APERCU
        assert c["justification"]["resume"].startswith("Probabilité NON calibrée")
        assert "calibrée." not in c["justification"]["preuves"][-1]["texte"].replace("NON calibrée.", "")


@pytest.mark.parametrize("x", [_x(selections=[_selection()], apercu=[_selection("1x2_1")]),  # vraie sélection : prioritaire
                               _x(), _x(selections=[_selection()])])
def test_pas_d_apercu_si_selection_ou_rien(x):
    s = mp.signal_site(x)["moteur_v3"]
    assert s["apercu_non_calibre"] is False
    assert all(not c["apercu_non_calibre"] and mp.VIGILANCE_APERCU not in c["points_de_vigilance"]
               and c["justification"]["resume"].startswith("Probabilité calibrée") for c in s["selection"].values())


def test_apercu_seulement_sans_calibration(tmp_path):
    d, sortie = str(tmp_path / "archive"), str(tmp_path / "v3" / "pronostics_v3.json")
    _ecrit(d, [_enreg("ok")])
    mp.execution(dossier=d, fichier_sortie=sortie, maintenant=MAINTENANT)
    with open(sortie, encoding="utf-8") as f:
        out = json.load(f)
    assert out["calibration"]["prete"] is False and out["matchs"][0]["selections"] == []
    assert "apercu_non_calibre" in out["matchs"][0] and "matchs_en_apercu_non_calibre" in out["bilan"]
    for a in out["matchs"][0]["apercu_non_calibre"]:          # tous les autres contrôles restent appliqués
        assert 1.26 <= a["cote"] <= 1.74 and a["probabilite"] >= 0.60 and a["justification"]


def test_page_v3_affiche_l_apercu():
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(racine, "archetype_v3.js"), encoding="utf-8") as f:
        js = f.read()
    assert "apercu_non_calibre" in js and "Aperçu" in js and "Probabilité NON calibrée" in js


# --- AJOUT 28/09/2026 : journal V3 figé au coup d'envoi + empreinte du code (contrôle sans ambiguïté) ------------------

def _lance(tmp_path, enregs, maintenant):
    d, sortie = str(tmp_path / "archive"), str(tmp_path / "v3" / "pronostics_v3.json")
    _ecrit(d, enregs)
    bilan = mp.execution(dossier=d, fichier_sortie=sortie, maintenant=maintenant)
    chemin = tmp_path / "v3" / "journal" / "2026-09-28.json"
    return bilan, (json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {})


@pytest.mark.parametrize("heure", [6, 12, 17])          # avant le coup d'envoi (18:00 UTC) : le calcul est journalisé
def test_journal_ecrit_avant_le_coup_d_envoi(tmp_path, heure):
    t = datetime.datetime(2026, 9, 28, heure, 0, tzinfo=datetime.timezone.utc)
    bilan, j = _lance(tmp_path, [_enreg("ok")], t)
    e = j["ok"]
    assert bilan["journal_ecrits"] == 1 and e["calcule_le"] == t.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert e["empreinte_code_v3"] == mp.empreinte_code() and e["statut"] == "EVALUE" and "apercu_non_calibre" in e
    assert e["calibration"]["prete"] is False


@pytest.mark.parametrize("heure", [18, 20, 23])         # coup d'envoi passé : l'entrée n'est plus jamais modifiée
def test_journal_fige_apres_le_coup_d_envoi(tmp_path, heure):
    avant = datetime.datetime(2026, 9, 28, 10, 0, tzinfo=datetime.timezone.utc)
    _, j1 = _lance(tmp_path, [_enreg("ok")], avant)
    apres = datetime.datetime(2026, 9, 28, heure, 0, tzinfo=datetime.timezone.utc)
    _, j2 = _lance(tmp_path, [_enreg("ok")], apres)
    assert j2 == j1 and j2["ok"]["calcule_le"] == "2026-09-28T10:00:00Z"


def test_journal_garde_le_dernier_calcul_avant_match(tmp_path):
    _lance(tmp_path, [_enreg("ok")], datetime.datetime(2026, 9, 28, 4, 0, tzinfo=datetime.timezone.utc))
    _, j = _lance(tmp_path, [_enreg("ok")], datetime.datetime(2026, 9, 28, 16, 0, tzinfo=datetime.timezone.utc))
    assert j["ok"]["premier_calcul_le"] == "2026-09-28T04:00:00Z" and j["ok"]["calcule_le"] == "2026-09-28T16:00:00Z"
    assert j["ok"]["nb_calculs"] == 2


def test_empreinte_change_si_le_code_change(tmp_path):
    for nom in ("moteur_v3_pipeline.py", "regles_selection.py", "banc_historique.py"):
        (tmp_path / nom).write_text("a = 1\n", encoding="utf-8")
    (tmp_path / "moteur_v3").mkdir()
    (tmp_path / "moteur_v3" / "model.py").write_text("K = 4\n", encoding="utf-8")
    e1 = mp.empreinte_code(str(tmp_path))
    assert mp.empreinte_code(str(tmp_path)) == e1                   # même code : même empreinte
    (tmp_path / "moteur_v3" / "model.py").write_text("K = 5\n", encoding="utf-8")
    assert mp.empreinte_code(str(tmp_path)) != e1                   # une ligne changée : empreinte différente


# --- AJOUT 28/09/2026 : calibration seulement à partir de 50 matchs joués (décision de Patrick) -------------------------

def _joues(n):
    return [_enreg(f"j{i}", date="2026-09-20", score=(i % 3, (i // 3) % 2)) for i in range(n)]


@pytest.mark.parametrize("n", [50, 60, 100])
def test_calibration_prete_a_partir_de_50_matchs(n):
    cal, matchs = mp.entraine_calibration(_joues(n), "2026-09-27")
    assert matchs == n and cal.fit_result.ready and cal.predict(0.5) is not None


@pytest.mark.parametrize("n", [34, 40, 49])            # >= 300 observations, mais moins de 50 matchs
def test_calibration_refusee_sous_50_matchs(n):
    cal, matchs = mp.entraine_calibration(_joues(n), "2026-09-27")
    assert matchs == n and cal.fit_result.observations >= 300
    assert not cal.fit_result.ready and cal.fit_result.reason == "MATCHS_INSUFFISANTS" and cal.predict(0.5) is None


# --- AJOUT 28/09/2026 : TOUS les marchés cotés par BetPawa calculés (handicaps, score exact, pair/impair, lignes hautes) --

from moteur_v3.markets import gagne  # noqa: E402
from moteur_v3.model import build_model as _build  # noqa: E402
from moteur_v3.markets import derive_markets as _derive  # noqa: E402


def _cotes_bp(**groupes):
    return mp.cotes_etendues({"cotes_betpawa": groupes, "cotes_observees": {}})


@pytest.mark.parametrize("groupes,attendu", [
    ({"handicap_-0.5": {"domicile": 2.9, "exterieur": 1.4}}, {"handicap_0.5_1": 2.9, "handicap_0.5_2": 1.4}),
    ({"score_exact": {"2-1": 8.5}, "pair_impair": {"pair": 1.8, "impair": 1.9}},
     {"score_2_1": 8.5, "total_pair": 1.8, "total_impair": 1.9}),
    ({"over_under_6.5": {"plus": 21.0, "moins": 1.01}, "over_under_domicile_2.5": {"plus": 4.0, "moins": 1.2}},
     {"over_6_5": 21.0, "under_6_5": 1.01, "home_over_2_5": 4.0, "home_under_2_5": 1.2}),
])
def test_cotes_etendues_lues(groupes, attendu):
    assert _cotes_bp(**groupes) == attendu


@pytest.mark.parametrize("groupes", [
    {"handicap_-1": {"domicile": 2.0, "exterieur": 1.8}},          # ligne entière (3 issues possibles) : ignorée
    {"handicap_3choix_1": {"domicile": 2.0}},                     # autre forme de handicap : ignorée
    {"score_exact": {"autre": 9.0, "1-0": 1.0}},                  # issue illisible et cote <= 1 : ignorées
])
def test_cotes_etendues_rien_d_invente(groupes):
    assert _cotes_bp(**groupes) == {}


def _probas():
    e = _enreg("m")
    return _derive(_build(e["equipe_dom"]["matchs"], e["equipe_ext"]["matchs"]), [0.5, -0.5, 1.5])


@pytest.mark.parametrize("handicap,equivalent", [("handicap_0.5_1", "1x2_1"), ("handicap_-0.5_1", "dc_1X"),
                                                 ("handicap_0.5_2", "dc_X2")])
def test_handicap_meme_probabilite_que_le_marche_equivalent(handicap, equivalent):
    p = _probas()
    assert abs(p[handicap] - p[equivalent]) < 1e-12


@pytest.mark.parametrize("handicap,different", [("handicap_1.5_1", "1x2_1"), ("handicap_-0.5_1", "1x2_1"),
                                                ("handicap_0.5_2", "1x2_2")])
def test_handicap_different_des_autres_marches(handicap, different):
    p = _probas()
    assert abs(p[handicap] - p[different]) > 1e-6


@pytest.mark.parametrize("marche,score", [("score_2_1", (2, 1)), ("total_pair", (1, 1)), ("clean_home_no", (0, 1))])
def test_resultat_reel_nouveaux_marches_gagnes(marche, score):
    assert gagne(marche, *score) is True


@pytest.mark.parametrize("marche,score", [("score_2_1", (1, 2)), ("total_pair", (2, 1)), ("clean_home_no", (1, 0))])
def test_resultat_reel_nouveaux_marches_perdus(marche, score):
    assert gagne(marche, *score) is False


def test_resultat_reel_identique_au_banc_sur_tous_les_marches_communs():
    import banc_historique as bh
    for v3, banc in mp.V3_VERS_BANC.items():
        for h in range(7):
            for a in range(7):
                assert gagne(v3, h, a) == bool(bh.gagne(banc, h, a)), (v3, h, a)


def test_scores_et_parite_somment_correctement():
    p = _probas()
    assert abs(p["total_pair"] + p["total_impair"] - 1) < 1e-12
    assert 0.9 < sum(v for k, v in p.items() if k.startswith("score_")) <= 1 + 1e-12


@pytest.mark.parametrize("marche,site", [("handicap_0.5_1", "handicap_domicile_-0.5"),
                                         ("handicap_-1.5_1", "handicap_domicile_1.5"),
                                         ("handicap_-0.5_2", "handicap_exterieur_-0.5")])
def test_nom_site_des_handicaps(marche, site):
    assert mp.nom_site(marche) == site


def test_couverture_signale_les_groupes_non_lus():
    e = {"cotes_betpawa": {"1x2": {"1": 2.0}, "handicap_-0.5": {"domicile": 2.0}, "handicap_3choix_1": {"1": 3.0},
                           "mi_temps_1x2": {"1": 3.0}}}
    c = mp.couverture(e, {})
    assert c["groupes_non_lus"] == ["handicap_3choix_1", "mi_temps_1x2"] and c["issues_betpawa"] == 4


def test_journal_contient_le_diagnostic_de_tous_les_marches(tmp_path):
    _, j = _lance(tmp_path, [_enreg("ok")], datetime.datetime(2026, 9, 28, 6, 0, tzinfo=datetime.timezone.utc))
    lignes = j["ok"]["tous_les_marches"]
    assert {l[0] for l in lignes} == set(mp.cotes_v3(_enreg("ok"))) and all(len(l) == 5 for l in lignes)


# --- AJOUT 28/09/2026 : standard de justification V3 (6 blocs + alertes) et règle du double contrôle 1.2.0 -------------

BLOCS = ["Données", "Buts attendus", "Probabilité", "Face à la cote", "Contrôles", "Pourquoi ce marché"]


def _apercus_reels():
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(racine, "tests", "fixtures", "v3_matchs_reels_2709.json"), encoding="utf-8") as f:
        enregs = json.load(f)["enregistrements"]
    out = []
    for e in enregs:
        x = mp.evalue_enregistrement(e, None)
        out += [(e, a) for a in x.get("apercu_non_calibre", [])]
    return out


def test_explication_six_blocs_dans_l_ordre():
    ap = _apercus_reels()
    assert ap, "au moins un aperçu attendu sur les vrais matchs du 27/09"
    for _, a in ap:
        ex = a["explication"]
        assert [b["titre"] for b in ex["blocs"]] == BLOCS and all(b["lignes"] for b in ex["blocs"])
        assert ex["alertes"][0].startswith("Aperçu non calibré")


def test_explication_chiffres_coherents():
    for e, a in _apercus_reels():
        bloc = {b["titre"]: b["lignes"] for b in a["explication"]["blocs"]}
        assert f"Cote {a['cote']:.2f}".replace(".", ",") in bloc["Face à la cote"][0]
        assert f"{100 * a['probabilite']:.1f}".replace(".", ",") in bloc["Probabilité"][0]
        assert e["domicile"] in bloc["Données"][0] and e["exterieur"] in bloc["Données"][1]


@pytest.mark.parametrize("marche,attendu", [("1x2_1", "domicile > extérieur"), ("under_3_5", "au plus 3 buts"),
                                            ("handicap_1.5_1", "buts domicile − 1,5 > buts extérieur")])
def test_phrase_de_calcul_par_famille(marche, attendu):
    assert attendu in mp.phrase_calcul(marche)


@pytest.mark.parametrize("args,attendu", [((0.82, 1.52, 3, (3.5, 0.9), 1.3, True), 5),
                                          ((0.72, 1.60, 4, (1.5, 1.1), 0.8, False), 1),
                                          ((0.75, 1.44, 4, (2.4, 2.1), 0.9, False), 2)])
def test_alertes_declenchees(args, attendu):
    assert len(mp.alertes(*args)) == attendu


@pytest.mark.parametrize("args", [(0.70, 1.55, 8, (1.4, 1.1), 0.9, False), (0.65, 1.62, 6, (1.6, 1.2), 1.1, False),
                                  (0.68, 1.50, 10, (1.3, 1.3), 1.0, False)])
def test_aucune_alerte_sur_un_cas_normal(args):
    assert mp.alertes(*args) == []


def test_tous_les_marches_regles_existent():
    import regles_selection as rs
    assert all(v in rs.MARCHES_COUVERTS for v in mp.DOUBLE_CONTROLE.values())


@pytest.mark.parametrize("marche,regle", [("handicap_0.5_1", "1X2 - 1"), ("handicap_-0.5_2", "1X2 - 2"),
                                          ("clean_home_no", "Buts extérieur - plus de 0.5")])
def test_marches_equivalents_meme_regle(marche, regle):
    assert mp.DOUBLE_CONTROLE[marche] == regle


@pytest.mark.parametrize("marche", ["score_1_0", "exact_goals_2", "total_pair"])
def test_marches_non_justifiables_restent_hors_regle(marche):
    assert marche not in mp.DOUBLE_CONTROLE
