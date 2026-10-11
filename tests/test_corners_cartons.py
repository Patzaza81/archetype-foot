"""Rubrique corners / cartons (11/10/2026) : lois, modèle sans fuite, rapprochement des noms, règlement, bout en bout.
Cas qui doivent réussir et cas qui doivent échouer. Bibliothèque standard + pytest uniquement."""
import datetime
import json
import math

import pytest

import corners_cartons as cc


def match(date, dom, ext, hc, ac, hy=1, ay=2, hr=0, ar=0, div="E0", saison="2627"):
    return {"competition_code": div, "season": saison, "date": date, "home_team": dom, "away_team": ext,
            "full_time_home_goals": 1, "full_time_away_goals": 0, "home_corners": hc, "away_corners": ac,
            "home_yellow_cards": hy, "away_yellow_cards": ay, "home_red_cards": hr, "away_red_cards": ar}


# --- Lois : valeurs de référence calculées avec scipy (nbinom / poisson) le 11/10/2026 -------------------------------
@pytest.mark.parametrize("mu,alpha,ligne,attendu", [
    (9.5, 0.021, 9.5, 0.47217), (4.9, 0.115, 4.5, 0.506268), (3.8, 0.0163, 3.5, 0.521604),
    (2.1, 0.0, 1.5, 0.620385), (11.2, 0.021, 12.5, 0.341865), (1.4, 0.115, 0.5, 0.72695),
])
def test_loi_conforme_aux_valeurs_de_reference(mu, alpha, ligne, attendu):
    assert cc.proba_plus_de(mu, alpha, ligne) == pytest.approx(attendu, abs=1e-5)


def test_loi_plus_de_decroit_avec_la_ligne_et_reste_entre_0_et_1():
    ps = [cc.proba_plus_de(9.6, 0.021, l) for l in (7.5, 8.5, 9.5, 10.5, 11.5, 12.5)]
    assert ps == sorted(ps, reverse=True) and all(0.0 <= p <= 1.0 for p in ps)
    assert cc.proba_plus_de(0.0, 0.1, 0.5) == 0.0


# --- Modèle : pas de fuite, shrinkage, compression -----------------------------------------------------------------
def test_aucune_prevision_tant_que_rien_n_a_ete_observe():
    assert cc.ModeleComptage(40, 0.7).predit("E0", "A", "B") is None


def test_la_prevision_ne_voit_jamais_le_match_qu_elle_predit():
    mod = cc.ModeleComptage(5, 1.0)
    mod.observe("E0", "A", "B", 6, 4)
    avant = mod.predit("E0", "A", "B")
    assert avant[4] == 1 and avant[5] == 1     # au moment de la prévision : un seul match connu pour chaque équipe
    mod.observe("E0", "A", "B", 12, 1)         # le match observé après n'a pas pu influencer la prévision déjà faite
    assert mod.predit("E0", "A", "B")[4] == 2


def test_equipe_a_beaucoup_de_corners_depasse_la_moyenne_mais_reste_tiree_vers_elle():
    mod = cc.ModeleComptage(10, 1.0)
    for i in range(12):
        mod.observe("E0", "Fort", f"X{i % 3}", 10, 3)
        mod.observe("E0", f"Y{i % 3}", f"Z{i % 3}", 5, 4)
    mu_d, mu_e, base_d, base_e, nd, ne = mod.predit("E0", "Fort", "Y0")
    assert mu_d > base_d and base_d < 10     # au-dessus de la moyenne de la division
    assert mu_d < 10                          # mais tiré vers elle (pas la moyenne brute de l'équipe)
    assert nd == 12


def test_compression_c_rapproche_de_la_moyenne_de_la_division():
    mods = {c: cc.ModeleComptage(5, c) for c in (0.0, 0.5, 1.0)}
    for mod in mods.values():
        for i in range(10):
            mod.observe("E0", "Fort", "Y", 9, 3)
            mod.observe("E0", "M", "N", 5, 4)
    mu = {c: m.predit("E0", "Fort", "Neutre")[0] for c, m in mods.items()}      # adversaire inconnu : facteur 1
    base = mods[0.0].predit("E0", "Fort", "Neutre")[2]
    assert mu[0.0] == pytest.approx(base) and base < mu[0.5] < mu[1.0]


# --- Données : saison en cours seule ---------------------------------------------------------------------------------
def test_charge_la_saison_la_plus_recente_seulement(tmp_path):
    for saison, equipe in (("2526", "Ancienne"), ("2627", "Courante")):
        d = tmp_path / saison
        d.mkdir()
        (d / "E0.jsonl").write_text(json.dumps(match("2026-09-01", equipe, "B", 5, 4)) + "\n", encoding="utf-8")
    saison, matchs = cc.charge_matchs_saison(str(tmp_path))
    assert saison == "2627" and [m["home_team"] for m in matchs] == ["Courante"]


def test_donnee_absente_n_est_jamais_remplacee_par_zero():
    m = match("2026-09-01", "A", "B", 5, 4)
    m["home_corners"] = None
    assert cc._comptes(m, "corners") is None and cc._comptes(m, "cartons") == (1, 2)
    m["away_yellow_cards"] = None
    assert cc._comptes(m, "cartons") is None


def test_cartons_comptent_jaunes_et_rouges():
    assert cc._comptes(match("2026-09-01", "A", "B", 5, 4, hy=2, ay=1, hr=1, ar=1), "cartons") == (3, 2)
    assert cc._comptes(match("2026-09-01", "A", "B", 5, 4, hr=1, ar=0), "rouge") == (1, 0)


# --- Rapprochement des noms : 3 cas qui passent, 3 qui échouent ------------------------------------------------------
CORR = {"divisions": {
    "E0": {"competition_matchendirect": "Angleterre : Premier League",
           "equipes": {"Man United": {"matchendirect": "Manchester United", "preuves": 4},
                       "Arsenal": {"matchendirect": "Arsenal", "preuves": 5},
                       "Spurs": {"matchendirect": "Tottenham", "preuves": 3},
                       "Dup1": {"matchendirect": "Doublon", "preuves": 2}, "Dup2": {"matchendirect": "Doublon", "preuves": 2}}},
    "EGY": {"competition_matchendirect": "Egypte : Premier League",
            "equipes": {"Al Ahly": {"matchendirect": "Al Ahly", "preuves": 3}, "Zamalek": {"matchendirect": "Zamalek", "preuves": 3}}},
}}
IDX = cc.construit_index(CORR)


@pytest.mark.parametrize("comp,dom,ext,attendu", [
    ("Angleterre : Premier League", "Manchester United", "Arsenal", ("E0", "Man United", "Arsenal")),
    ("Angleterre :\n      Premier League", "MANCHESTER UNITED", "Tottenham", ("E0", "Man United", "Spurs")),
    ("Egypte : Premier League", "Al Ahly", "Zamalek", ("EGY", "Al Ahly", "Zamalek")),
])
def test_rapprochement_reussit(comp, dom, ext, attendu):
    assert cc.trouve_equipes(comp, dom, ext, *IDX) == attendu


@pytest.mark.parametrize("comp,dom,ext", [
    ("Nigeria : Premier League", "Manchester United", "Arsenal"),         # même nom de ligue, autre pays
    ("Angleterre : Premier League", "Manchester United", "Inconnu FC"),   # équipe non reliée
    ("Angleterre : Premier League", "Doublon", "Arsenal"),                # nom revendiqué par deux équipes
])
def test_rapprochement_echoue(comp, dom, ext):
    assert cc.trouve_equipes(comp, dom, ext, *IDX) is None


def test_meme_equipe_a_domicile_et_a_l_exterieur_refusee():
    assert cc.trouve_equipes("Angleterre : Premier League", "Arsenal", "Arsenal", *IDX) is None


# --- Règlement ---------------------------------------------------------------------------------------------------------
PREV = {"corners": {"total": {"8.5": 0.6, "9.5": 0.5}, "domicile": {"4.5": 0.5}, "exterieur": {"4.5": 0.4}},
        "cartons": {"total": {"3.5": 0.5}, "domicile": {"1.5": 0.5}, "exterieur": {"1.5": 0.5}}, "rouge": {"oui": 0.15}}


def test_reglement_corners_cartons_rouge():
    obs = cc.observations(match("2026-09-01", "A", "B", 6, 4, hy=2, ay=1, hr=0, ar=1))
    r = cc.regle_prevision(PREV, obs)
    assert r["corners"]["total"] == {"8.5": True, "9.5": True}
    assert r["corners"]["domicile"]["4.5"] is True and r["corners"]["exterieur"]["4.5"] is False   # 6 > 4,5 ; 4 < 4,5
    assert r["cartons"]["total"]["3.5"] is True and r["cartons"]["exterieur"]["1.5"] is True       # 4 cartons ; 2 > 1,5
    assert r["rouge"]["oui"] is True


def test_lignes_en_demi_unites_aucun_remboursement():
    obs = cc.observations(match("2026-09-01", "A", "B", 5, 4))
    r = cc.regle_prevision(PREV, obs)
    assert r["corners"]["total"]["8.5"] is True and r["corners"]["total"]["9.5"] is False   # 9 corners


def test_reglement_ignore_ce_dont_la_donnee_reelle_manque():
    m = match("2026-09-01", "A", "B", 5, 4)
    m["away_corners"] = None
    r = cc.regle_prevision(PREV, cc.observations(m))
    assert "corners" not in r and "cartons" in r and "rouge" in r


# --- Refus d'un match ---------------------------------------------------------------------------------------------------
def _joue(n_par_equipe, div="E0", corners=True):
    matchs = []
    equipes = ["A", "B", "C", "D"]
    for i in range(n_par_equipe):
        d = f"2026-08-{10 + i:02d}"
        matchs += [match(d, "A", "B", 6, 4, div=div), match(d, "C", "D", 5, 5, div=div)]
        if i % 2:
            matchs += [match(d, "B", "C", 4, 6, div=div), match(d, "D", "A", 5, 4, div=div)]
    if not corners:
        for m in matchs:
            m["home_corners"] = m["away_corners"] = None
    return matchs


def test_match_prevu_quand_les_equipes_ont_assez_de_matchs():
    mods, dr, pr = cc.construit_modeles(_joue(8))
    prev, raison = cc.prevoit_match(mods, dr, pr, "E0", "A", "B")
    assert raison is None and set(prev["previsions"]) >= {"corners", "cartons", "rouge", "fiabilite"}
    assert prev["previsions"]["fiabilite"] in ("faible", "moyenne", "bonne")
    assert 0.0 < prev["previsions"]["rouge"]["oui"] < 1.0


def test_match_ecarte_si_equipe_sans_historique_suffisant():
    mods, dr, pr = cc.construit_modeles(_joue(1))
    prev, raison = cc.prevoit_match(mods, dr, pr, "E0", "A", "Nouvelle")
    assert prev is None and raison == "echantillon_insuffisant"


def test_match_ecarte_si_le_championnat_ne_publie_ni_corners_ni_cartons():
    mods, dr, pr = cc.construit_modeles(_joue(8) + _joue(8, div="ARG", corners=False))
    prev, raison = cc.prevoit_match(mods, dr, pr, "ARG", "A", "B")
    assert prev is None and raison == "corners_cartons_non_publies_pour_ce_championnat"


# --- Bout en bout : prévision, archive, règlement, bilan ---------------------------------------------------------------
def _installe(tmp_path, monkeypatch, matchs, signaux):
    norm = tmp_path / "normalized" / "2627"
    norm.mkdir(parents=True, exist_ok=True)
    (norm / "E0.jsonl").write_text("\n".join(json.dumps(m) for m in matchs) + "\n", encoding="utf-8")
    (tmp_path / "corr.json").write_text(json.dumps({"divisions": {"E0": {
        "competition_matchendirect": "Angleterre : Premier League",
        "equipes": {n: {"matchendirect": n, "preuves": 3} for n in "ABCD"}}}}), encoding="utf-8")
    (tmp_path / "precalcul.json").write_text(json.dumps({"signaux": signaux}), encoding="utf-8")
    monkeypatch.setattr(cc, "DOSSIER_NORMALISE", str(tmp_path / "normalized"))
    monkeypatch.setattr(cc, "FICHIER_CORRESPONDANCES", str(tmp_path / "corr.json"))
    monkeypatch.setattr(cc, "FICHIER_PRECALCUL", str(tmp_path / "precalcul.json"))
    monkeypatch.setattr(cc, "FICHIER_SORTIE", str(tmp_path / "out" / "corners_cartons.json"))
    monkeypatch.setattr(cc, "FICHIER_ARCHIVE", str(tmp_path / "out" / "archive.json"))


def _signal(mid, dom, ext, date, score=None):
    return {"match_id": mid, "domicile": dom, "exterieur": ext, "competition": "Angleterre : Premier League",
            "date": date, "heure_cameroun": "15:00", "score": score}


def test_bout_en_bout_prevision_puis_reglement(tmp_path, monkeypatch):
    joues = _joue(8)
    _installe(tmp_path, monkeypatch, joues, [_signal("m1", "A", "B", "2026-10-12"), _signal("m2", "A", "B", "2026-10-13", "1-0"),
                                             _signal("m3", "A", "Z", "2026-10-12")])
    assert cc.main(datetime.date(2026, 10, 11)) == 0
    sortie = json.loads((tmp_path / "out" / "corners_cartons.json").read_text(encoding="utf-8"))
    assert [m["match_id"] for m in sortie["matchs"]] == ["m1"]           # m2 a déjà un score, m3 : équipe inconnue
    assert sortie["refus"] == {"equipes_non_reliees_a_football_data": 1}
    assert sortie["bilan"]["matchs_regles"] == 0
    archive = json.loads((tmp_path / "out" / "archive.json").read_text(encoding="utf-8"))
    assert list(archive) == ["m1"] and "reglement" not in archive["m1"]

    # Football-Data publie le match joué le 12/10 : règlement, et plus aucune nouvelle prévision pour lui
    joues.append(match("2026-10-12", "A", "B", 7, 5, hy=3, ay=2))
    _installe(tmp_path, monkeypatch, joues, [_signal("m1", "A", "B", "2026-10-12")])
    cc.main(datetime.date(2026, 10, 12))
    sortie = json.loads((tmp_path / "out" / "corners_cartons.json").read_text(encoding="utf-8"))
    archive = json.loads((tmp_path / "out" / "archive.json").read_text(encoding="utf-8"))
    assert sortie["matchs"] == [] and sortie["refus"] == {"deja_joue_dans_football_data": 1}
    assert archive["m1"]["reglement"]["corners"]["reel"] == {"domicile": 7, "exterieur": 5}
    assert archive["m1"]["reglement"]["corners"]["total"]["11.5"] is True        # 12 corners
    assert sortie["bilan"]["matchs_regles"] == 1
    fam = sortie["bilan"]["familles"]
    assert {"corners_total", "cartons_total", "rouge_match"} <= set(fam)
    assert fam["corners_total"]["logloss_moyenne_division_seule"] is not None


def test_une_prevision_reglee_n_est_plus_jamais_modifiee(tmp_path, monkeypatch):
    joues = _joue(8) + [match("2026-10-12", "A", "B", 7, 5)]
    _installe(tmp_path, monkeypatch, joues, [])
    archive = {"m1": {"match_id": "m1", "date": "2026-10-12", "division": "E0", "nom_fd_domicile": "A",
                      "nom_fd_exterieur": "B", "previsions": PREV, "reglement": {"corners": {"reel": {}}}, "base_ligue": {}}}
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "archive.json").write_text(json.dumps(archive), encoding="utf-8")
    (tmp_path / "precalcul.json").write_text(json.dumps({"signaux": [_signal("m1", "A", "B", "2026-10-14")]}), encoding="utf-8")
    cc.main(datetime.date(2026, 10, 11))
    apres = json.loads((tmp_path / "out" / "archive.json").read_text(encoding="utf-8"))
    assert apres["m1"]["previsions"] == PREV and apres["m1"]["reglement"] == {"corners": {"reel": {}}}
