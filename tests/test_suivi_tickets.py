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
