import copy

import pytest

import generateur_tickets as gt
import suivi_tickets as st

MAINT = "2026-10-08T10:00:00+00:00"


def ev(marche, h, a):
    """Évaluateur injecté : le nom du marché décide du résultat."""
    return {"W": "WIN", "L": "LOSS", "V": "VOID"}.get(marche)


def legs12(marches=None, source="moteur_v2_6_10"):
    marches = marches or ["W"] * 12
    out = []
    for i in range(12):
        out.append({"match_id": str(i), "date": "2026-10-08", "domicile": "A", "exterieur": "B", "marche": marches[i],
                    "cote": 1.7, "probabilite_estimee": 0.7, "source": source, "rang": "P1"})
    return out


def tickets_json(legs=None, scenario="EQUILIBRE_12"):
    legs = legs or legs12()
    return {"genere_le": MAINT, "scenarios": [{"scenario": scenario, "statut": "OK", "selection": legs,
                                               "metrics": {"cote_totale": 1.7 ** 12}, "analyse": gt.analyse_ticket(legs)}]}


SCORES = {str(i): (1, 0) for i in range(12)}


def plan4x3(entry):
    return next(p for p in entry["analyse"]["plans"] if p["nom"] == "TICKETS_4X3")


def regle_avec(marches):
    h = st.enregistre([], tickets_json(legs12(marches)), {}, MAINT)
    return st.regle(h[0], SCORES, ev)


def test_enregistrement_est_idempotent():
    h1 = st.enregistre([], tickets_json(), {}, MAINT)
    h2 = st.enregistre(copy.deepcopy(h1), tickets_json(), {}, MAINT)
    assert len(h1) == len(h2) == 1
    assert h2[0]["cle"] == "2026-10-08|EQUILIBRE_12"


def test_une_entree_en_attente_sans_score_est_remplacee_par_la_version_recente():
    h1 = st.enregistre([], tickets_json(), {}, MAINT)
    nouveau = tickets_json(legs12(source="moteur_v3"))
    h2 = st.enregistre(h1, nouveau, {}, MAINT)
    assert len(h2) == 1 and h2[0]["jambes"][0]["source"] == "moteur_v3"


def test_une_entree_avec_un_score_connu_est_figee():
    h1 = st.enregistre([], tickets_json(), {}, MAINT)
    h2 = st.enregistre(h1, tickets_json(legs12(source="moteur_v3")), {"3": (1, 0)}, MAINT)
    assert h2[0]["jambes"][0]["source"] == "moteur_v2_6_10"


def test_une_entree_reglee_n_est_jamais_modifiee():
    e = regle_avec(["W"] * 12)
    assert e["statut"] == "RESOLVED"
    h2 = st.enregistre([e], tickets_json(legs12(source="moteur_v3")), {}, MAINT)
    assert h2[0]["jambes"][0]["source"] == "moteur_v2_6_10" and h2[0]["statut"] == "RESOLVED"


@pytest.mark.parametrize("t", [
    {"scenarios": [{"scenario": "X", "statut": "AUCUN_TICKET_SOLIDE", "selection": [], "analyse": None}]},
    {"scenarios": []},
    {},
])
def test_rien_a_enregistrer_sans_ticket_solide(t):
    assert st.enregistre([], t, {}, MAINT) == []


def test_trois_perdants_dans_trois_tickets_differents_laissent_un_ticket_gagnant_rentable():
    base = st.enregistre([], tickets_json(), {}, MAINT)[0]
    p = plan4x3(base)
    marches = ["W"] * 12
    for t in p["composition"][:3]:
        marches[t["paris"][0]] = "L"
    e = regle_avec(marches)
    r = next(x for x in e["resultat"]["plans"] if x["nom"] == "TICKETS_4X3")
    assert e["resultat"]["erreurs"] == 3
    assert r["tickets_gagnants"] == 1 and r["rentable"] is True and r["profit"] > 0


def test_trois_perdants_dans_le_meme_ticket_laissent_trois_tickets_gagnants():
    base = st.enregistre([], tickets_json(), {}, MAINT)[0]
    p = plan4x3(base)
    marches = ["W"] * 12
    for i in p["composition"][0]["paris"]:
        marches[i] = "L"
    e = regle_avec(marches)
    r = next(x for x in e["resultat"]["plans"] if x["nom"] == "TICKETS_4X3")
    assert r["tickets_gagnants"] == 3 and r["rentable"] is True


def test_tous_les_paris_perdus_donnent_une_perte_totale():
    e = regle_avec(["L"] * 12)
    r = next(x for x in e["resultat"]["plans"] if x["nom"] == "TICKETS_4X3")
    assert r["tickets_gagnants"] == 0 and r["rentable"] is False and r["profit"] == -1.0


def test_un_pari_annule_exclut_le_ticket_des_statistiques():
    marches = ["W"] * 11 + ["V"]
    e = regle_avec(marches)
    assert e["statut"] == "EXCLU"


def test_un_score_manquant_laisse_le_ticket_en_attente():
    h = st.enregistre([], tickets_json(), {}, MAINT)
    e = st.regle(h[0], {str(i): (1, 0) for i in range(11)}, ev)
    assert e["statut"] == "PENDING"


def test_marche_non_reconnu_exclut_le_ticket():
    e = regle_avec(["W"] * 11 + ["?"])
    assert e["statut"] == "EXCLU"


def test_bilan_agrege_les_tickets_regles():
    h = st.enregistre([], tickets_json(), {}, MAINT)
    h2 = st.enregistre([], tickets_json(scenario="AUTRE"), {}, MAINT)
    gagnant = st.regle(h[0], SCORES, ev)
    perdant_legs = legs12(["L"] * 12)
    perdant = st.regle(st.enregistre([], tickets_json(perdant_legs, "PERDU"), {}, MAINT)[0], SCORES, ev)
    attente = h2[0]
    b = st.bilan([gagnant, perdant, attente], MAINT)
    assert b["comptes"] == {"total": 3, "regles": 2, "en_attente": 1, "exclus": 0}
    assert b["par_scenario"]["EQUILIBRE_12"]["justes_observes"] == 12
    assert b["par_scenario"]["PERDU"]["erreurs"] == {"12": 1}
    p = b["par_scenario"]["PERDU"]["plans"]["TICKETS_4X3"]
    assert p["taux_rentable_observe"] == 0.0 and p["roi_observe"] == -1.0
    src = b["par_source"]["moteur_v2_6_10"]
    assert src["paris"] == 24 and src["taux_reussite"] == 0.5
    assert abs(src["proba_moyenne_estimee"] - 0.7) < 1e-9


def test_met_a_jour_enregistre_regle_et_produit_le_bilan():
    h, b = st.met_a_jour(tickets_json(), [], SCORES, ev, MAINT)
    assert h[0]["statut"] == "RESOLVED" and b["comptes"]["regles"] == 1


@pytest.mark.parametrize("marche,score,attendu", [
    ("1X2 - 1", (2, 1), "WIN"),
    ("Double chance - 1X", (0, 1), "LOSS"),
    ("Plus de 2.5 buts", (2, 1), "WIN"),
    ("Moins de 2.5 buts", (2, 1), "LOSS"),
    ("BTTS - non", (2, 0), "WIN"),
    ("over_2_5", (3, 0), "WIN"),
    ("1x2_domicile", (0, 0), "LOSS"),
])
def test_evaluateur_reel_comprend_libelles_et_cles(marche, score, attendu):
    assert st.evaluateur_defaut()(marche, *score) == attendu


@pytest.mark.parametrize("marche", ["", "Marché inventé", "Corners plus de 9.5 xyz"])
def test_evaluateur_reel_ne_devine_pas(marche):
    assert st.evaluateur_defaut()(marche, 2, 1) is None


def test_un_marche_non_reconnu_avec_score_exclut_le_ticket_au_lieu_de_rester_en_attente():
    h = st.enregistre([], tickets_json(legs12(["Marché inventé"] * 12)), {}, MAINT)
    e = st.regle(h[0], SCORES, st.evaluateur_defaut())
    assert e["statut"] == "EXCLU"


def test_construit_etat_lance_le_suivi_sans_jamais_bloquer(monkeypatch, capsys):
    import construit_etat_systeme as ces
    appels = []
    monkeypatch.setattr(st, "main", lambda: appels.append(1) or 0)
    ces.met_a_jour_suivi_tickets()
    assert appels == [1]
    monkeypatch.setattr(st, "main", lambda: (_ for _ in ()).throw(RuntimeError("boum")))
    ces.met_a_jour_suivi_tickets()          # ne lève pas
    assert "non mis à jour" in capsys.readouterr().out


def test_construit_suivi_tickets_garde_les_20_derniers(tmp_path, monkeypatch):
    import json
    import construit_etat_systeme as ces
    h = [{"date": f"2026-10-{i:02d}", "scenario": "S", "statut": "PENDING", "jambes": [1, 2]} for i in range(1, 31)]
    f = tmp_path / "h.json"
    f.write_text(json.dumps(h))
    monkeypatch.setattr(ces, "FICHIER_TICKETS_HISTORIQUE", str(f))
    monkeypatch.setattr(ces, "FICHIER_TICKETS_BILAN", str(tmp_path / "absent.json"))
    out = ces.construit_suivi_tickets()
    assert len(out["recents"]) == 20 and out["recents"][0]["date"] == "2026-10-30" and out["recents"][0]["paris"] == 2
    assert out["bilan"] == {}


# --- AJOUT 12/10/2026 (audit) : règlement des paris du Journal (sans match_id) et du handicap à 3 choix ---------------

def _jambe_journal(marche, dom="Queen's Park", ext="Inverness CT", date="2026-10-13", team=None):
    return {"match_id": None, "date": date, "domicile": dom, "exterieur": ext, "marche": marche, "cote": 1.3,
            "probabilite_estimee": 0.75, "source": "journal", "rang": None, "journal_team": team}


MATCHS = [{"match_id": "z9", "date": "2026-10-13", "domicile": "QUEEN'S PARK", "exterieur": "Inverness Ct", "buts": (1, 2)}]


def _regle_jambes(jambes, matchs=MATCHS, equipes=None):
    entry = {"cle": "k", "scenario": "S", "date": "2026-10-13", "statut": "PENDING", "jambes": jambes,
             "analyse": {"plans": []}, "resultat": None}
    return st.regle(entry, {}, st.evaluateur_defaut(), st.index_par_nom(matchs), equipes)


@pytest.mark.parametrize("marche,team,attendu", [
    ("Match à moins de 3,5 buts", None, "WIN"),          # 1-2 : 3 buts
    ("Les deux équipes marquent", None, "WIN"),
    ("Ne perd pas (victoire ou nul)", "Inverness CT", "WIN"),  # extérieur gagne : X2
])
def test_pari_du_journal_retrouve_par_date_et_noms_et_regle(marche, team, attendu):
    e = _regle_jambes([_jambe_journal(marche, team=team)])
    assert e["statut"] == "RESOLVED" and e["jambes"][0]["resultat"] == attendu


@pytest.mark.parametrize("jambe", [
    _jambe_journal("Match à moins de 3,5 buts", dom="Inverness CT", ext="Queen's Park"),  # équipes inversées
    _jambe_journal("Match à moins de 3,5 buts", date="2026-10-12"),                        # autre date
    _jambe_journal("Match à moins de 3,5 buts", ext="Ross County"),                         # autre adversaire
])
def test_pari_du_journal_sans_match_correspondant_reste_en_attente(jambe):
    e = _regle_jambes([jambe])
    assert e["statut"] == "PENDING" and e["jambes"][0]["resultat"] is None


def test_ne_perd_pas_sans_equipe_connue_n_est_jamais_devine():
    e = _regle_jambes([_jambe_journal("Ne perd pas (victoire ou nul)")])
    assert e["statut"] == "EXCLU"   # non reconnu : exclu des statistiques, jamais compté perdu


def test_equipe_du_journal_retrouvee_dans_l_archive_de_selection():
    equipes = st.equipes_journal({"executions": [{"paris": [
        {"date": "2026-10-13", "domicile": "Queen's Park", "exterieur": "Inverness CT",
         "marche": "Ne perd pas (victoire ou nul)", "journal_team": "Queen's Park"}]}]})
    e = _regle_jambes([_jambe_journal("Ne perd pas (victoire ou nul)")], equipes=equipes)
    assert e["jambes"][0]["resultat"] == "LOSS"   # domicile perd 1-2 : 1X perdant


@pytest.mark.parametrize("marche,h,a,attendu", [
    ("handicap3_domicile_1_1", 2, 2, "WIN"),    # domicile +1 : 3 > 2
    ("handicap3_domicile_1_X", 0, 1, "WIN"),    # 1 = 1
    ("handicap3_domicile_-2_2", 2, 1, "WIN"),   # domicile -2 : 0 < 1
    ("handicap3_domicile_1_1", 0, 1, "LOSS"),   # 1 = 1, pas >
    ("handicap3_domicile_-2_1", 2, 1, "LOSS"),  # 0 < 1
    ("handicap3_domicile_1_2", 2, 2, "LOSS"),   # 3 > 2
])
def test_handicap_a_trois_choix_est_regle(marche, h, a, attendu):
    assert st.evaluateur_defaut()(marche, h, a) == attendu


def test_handicap3_inconnu_reste_non_reconnu():
    assert st.evaluateur_defaut()("handicap3_domicile_1_Z", 1, 0) is None


def test_un_ticket_exclu_est_reevalue():
    entry = {"cle": "k", "scenario": "S", "date": "2026-10-13", "statut": "EXCLU", "resultat": {"raison": "x"},
             "jambes": [{"match_id": "a", "marche": "handicap3_domicile_1_1", "source": "moteur_v3", "date": "2026-10-13"}],
             "analyse": {"plans": []}}
    e = st.regle(entry, {"a": (2, 2)}, st.evaluateur_defaut())
    assert e["statut"] == "RESOLVED" and e["resultat"]["paris_justes"] == 1


# --- Tickets du même jour suivis en plus des tickets mélangés (14/10/2026) -------------------------------------------

def _legs_dates(dates, base=0):
    return [{"match_id": str(base + i), "date": d, "domicile": f"A{base + i}", "exterieur": "B", "marche": "W", "cote": 1.7,
             "probabilite_estimee": 0.7, "source": "moteur_v3", "rang": "P1"} for i, d in enumerate(dates)]


def _ticket(legs, scenario="PRUDENT_2"):
    return {"scenario": scenario, "statut": "OK", "selection": legs, "metrics": {"cote_totale": 2.9}, "analyse": gt.analyse_ticket(legs)}


def _tickets_avec_plage(large, jour):
    return {"genere_le": MAINT, "scenarios": [_ticket(large)], "plages": [{"scenarios": [_ticket(jour)]}]}


def test_ticket_du_jour_different_du_large_est_suivi_en_plus():
    t = _tickets_avec_plage(_legs_dates(["2026-10-14", "2026-10-15"]), _legs_dates(["2026-10-14", "2026-10-14"], base=10))
    h = st.enregistre([], t, {}, MAINT)
    assert sorted(e["cle"] for e in h) == ["2026-10-14|PRUDENT_2", "2026-10-14|PRUDENT_2|jour"]


def test_portee_meme_jour_et_melange():
    t = _tickets_avec_plage(_legs_dates(["2026-10-14", "2026-10-15"]), _legs_dates(["2026-10-14", "2026-10-14"], base=10))
    par_cle = {e["cle"]: e["portee"] for e in st.enregistre([], t, {}, MAINT)}
    assert par_cle == {"2026-10-14|PRUDENT_2": "melange", "2026-10-14|PRUDENT_2|jour": "meme_jour"}


def test_enregistrement_avec_plage_est_idempotent():
    t = _tickets_avec_plage(_legs_dates(["2026-10-14", "2026-10-15"]), _legs_dates(["2026-10-14", "2026-10-14"], base=10))
    h1 = st.enregistre([], t, {}, MAINT)
    assert st.enregistre(copy.deepcopy(h1), t, {}, MAINT) == h1


def test_ticket_du_jour_identique_au_large_n_est_pas_compte_deux_fois():
    legs = _legs_dates(["2026-10-14", "2026-10-14"])
    h = st.enregistre([], _tickets_avec_plage(legs, copy.deepcopy(legs)), {}, MAINT)
    assert [e["cle"] for e in h] == ["2026-10-14|PRUDENT_2"] and h[0]["portee"] == "meme_jour"


def test_sans_plages_le_comportement_historique_est_inchange():
    h = st.enregistre([], {"genere_le": MAINT, "scenarios": [_ticket(_legs_dates(["2026-10-14", "2026-10-15"]))]}, {}, MAINT)
    assert [e["cle"] for e in h] == ["2026-10-14|PRUDENT_2"]


def test_ticket_du_jour_non_ok_ou_sans_analyse_n_est_pas_suivi():
    large = _legs_dates(["2026-10-14", "2026-10-15"])
    vide = {"scenario": "PRUDENT_2", "statut": "AUCUN_TICKET_SOLIDE", "selection": [], "metrics": {}, "analyse": None}
    h = st.enregistre([], {"genere_le": MAINT, "scenarios": [_ticket(large)], "plages": [{"scenarios": [vide]}]}, {}, MAINT)
    assert [e["cle"] for e in h] == ["2026-10-14|PRUDENT_2"]


def test_bilan_separe_meme_jour_et_melange():
    jour = _legs_dates(["2026-10-14", "2026-10-14"], base=10)
    t = _tickets_avec_plage(_legs_dates(["2026-10-14", "2026-10-15"]), jour)
    scores = {str(i): (1, 0) for i in list(range(2)) + [10, 11]}
    h, b = st.met_a_jour(t, [], scores, ev, MAINT)
    assert b["par_portee"]["meme_jour"]["tickets_regles"] == 1 and b["par_portee"]["meme_jour"]["gagnants"] == 1
    assert b["par_portee"]["melange"]["tickets_regles"] == 1 and b["par_portee"]["melange"]["paris"] == 2
