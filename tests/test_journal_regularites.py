"""Journal, mode « regularites » : cote 1,26–1,56, indice de constance dès 6 matchs, probabilité de ticket = réussite
observée par tranche de cote, classement par Wilson, aucun ROI ni gain espéré.

Règle du dépôt : fonctions de comparaison testées sur au moins 3 cas qui passent et 3 qui échouent.
"""
import json

import pytest

import generateur_tickets as gt
import journal_regularites as jrg
import journal_rentabilite as jr
import selection_adaptative as sa

STATS = {"tranches": {1.3: (140, 200), 1.4: (130, 200), 1.5: (60, 100)}, "intervalle": (633, 1000), "erreur": None}


def _ligne(cote=1.40, gagnes=8, joues=10, g6=5, j6=6, roi=0.1, adv="Adv", equipe="Equipe Test",
           marche="Match à moins de 3,5 buts"):
    return {"equipe": equipe, "ligue": "Ligue Test", "marche": marche, "gagnes": gagnes, "joues": joues,
            "frequence": gagnes / joues, "frequence_generale": 0.5, "roi_betpawa": roi, "gagnes_6": g6, "joues_6": j6,
            "prochain_match": {"date": "2099-10-10", "heure": "15:00", "adversaire": adv, "lieu": "domicile",
                               "cote_betpawa": cote, "betpawa_url": "https://example.invalid/e"}}


def cand(stats=STATS, **kw):
    return sa._journal_team_market_candidate(_ligne(**kw), "regularites", stats)


# --- tranches et intervalle --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("cote,attendu", [(1.26, 1.2), (1.34, 1.3), (1.40, 1.4), (1.50, 1.5), (1.56, 1.5), (1.39, 1.3)])
def test_tranche_par_pas_de_dix_centiemes(cote, attendu):
    assert jrg.tranche(cote) == attendu


@pytest.mark.parametrize("cote", [1.26, 1.40, 1.56])
def test_dans_intervalle(cote):
    assert jrg.dans_intervalle(cote)


@pytest.mark.parametrize("cote", [1.25, 1.57, 1.80, 3.0, None, "abc"])
def test_hors_intervalle(cote):
    assert not jrg.dans_intervalle(cote)


# --- admissibilité : indice de constance ---------------------------------------------------------------------------------

@pytest.mark.parametrize("g,j,g6,j6,cote", [
    (10, 10, 6, 6, 1.40),      # parfait
    (7, 10, 6, 6, 1.50),       # (0,70 + 1,00) / 2 = 0,85
    (5, 5, None, None, 1.30),  # 5 matchs : réussite globale seule
    (6, 6, 5, 6, 1.26),        # 6 matchs : l'indice vaut la réussite globale (0,83)
    (8, 10, 4, 6, 1.56),       # (0,80 + 0,667) / 2 = 0,73
])
def test_admissible(g, j, g6, j6, cote):
    ok, motifs = jrg.evalue(g, j, g6, j6, cote)
    assert ok and motifs == []


@pytest.mark.parametrize("g,j,g6,j6,cote,motif", [
    (7, 10, 3, 6, 1.40, jrg.MOTIF_CONSTANCE),     # (0,70 + 0,50) / 2 = 0,60
    (8, 10, 2, 6, 1.40, jrg.MOTIF_CONSTANCE),     # (0,80 + 0,33) / 2 = 0,57
    (7, 10, None, None, 1.40, jrg.MOTIF_6_ABSENTS),  # dès 6 matchs la donnée est obligatoire
    (10, 10, 6, 6, 1.60, jrg.MOTIF_COTE),
    (10, 10, 6, 6, 1.20, jrg.MOTIF_COTE),
    (3, 4, None, None, 1.40, jrg.MOTIF_MATCHS),
])
def test_rejete(g, j, g6, j6, cote, motif):
    ok, motifs = jrg.evalue(g, j, g6, j6, cote)
    assert not ok and motif in motifs


def test_plus_de_plafond_1_80():
    ok, motifs = jrg.evalue(10, 10, 6, 6, 1.80)
    assert not ok and motifs == [jrg.MOTIF_COTE]   # 1,80 est maintenant hors intervalle (1,56 maximum)


# --- réussite observée --------------------------------------------------------------------------------------------------

def test_taux_tranche_si_assez_de_paris():
    taux, origine = jrg.taux_pour(1.35, STATS)
    assert (taux, origine) == (0.7, "tranche")


def test_taux_intervalle_si_tranche_trop_petite():
    taux, origine = jrg.taux_pour(1.52, STATS)    # tranche 1,5 : 100 paris < 200
    assert (taux, origine) == (0.633, "intervalle")


def test_taux_intervalle_si_tranche_vide():
    assert jrg.taux_pour(1.27, STATS) == (0.633, "intervalle")


@pytest.mark.parametrize("stats", [None, {}, {"tranches": {}, "intervalle": (0, 0)}])
def test_taux_absent(stats):
    assert jrg.taux_pour(1.40, stats) == (None, None)


def test_taux_observes_compte_tous_les_marches_et_ignore_hors_intervalle():
    matchs = [
        {"buts": (1, 0), "cotes": {"Plus de 0.5 buts": 1.30, "Moins de 0.5 buts": 1.40, "Plus de 2.5 buts": 2.0}},
        {"buts": (0, 0), "cotes": {"Plus de 0.5 buts": 1.35, "Moins de 0.5 buts": 1.45}},
    ]
    st = jrg.taux_observes(matchs)
    assert st["tranches"][1.3] == (1, 2)          # Plus de 0,5 : gagné puis perdu
    assert st["tranches"][1.4] == (1, 2)          # Moins de 0,5 : perdu puis gagné
    assert st["intervalle"] == (2, 4)             # le pari à 2,0 est hors intervalle


# --- candidat du Journal : ce qui est calculé et affiché ---------------------------------------------------------------

def test_probabilite_du_ticket_est_la_reussite_observee_pas_wilson():
    c = cand(cote=1.35)
    assert c["probabilite_source"] == "JOURNAL_REGULARITE"
    assert c["probabilite_estimee"] == 0.7 and c["journal_taux_origine"] == "tranche"
    assert c["journal_lower_bound"] < 0.7           # Wilson reste disponible, pour le classement seulement
    assert gt.proba(c) == 0.7


def test_aucun_roi_ni_gain_espere():
    c = cand()
    assert c["journal_roi"] is None and c["journal_success_margin"] is None
    ticket_leg = gt.leg(c)
    assert ticket_leg["ev_estime"] is None and ticket_leg["journal_roi"] is None


def test_affichage_x_sur_y_et_reussite_observee():
    c = cand(cote=1.35)
    assert c["journal_affichage"] == "8 sur 10"
    assert "8 sur 10" in c["justification"] and "70%" in c["justification"]
    assert "Wilson" not in c["justification"] and "80%" not in c["justification"]


def test_sans_taux_observe_le_pari_est_rejete():
    c = cand(stats={"tranches": {}, "intervalle": (0, 0), "erreur": "x"})
    assert c["journal_admissible"] is False and jrg.MOTIF_TAUX in c["journal_motifs_rejet"]
    assert not gt.eligible(c)


@pytest.mark.parametrize("cote", [1.30, 1.45, 1.56])
def test_eligible_dans_l_intervalle(cote):
    assert gt.eligible(cand(cote=cote))


@pytest.mark.parametrize("cote", [1.57, 1.80, 2.60])
def test_non_eligible_hors_intervalle(cote):
    c = cand(cote=cote)
    assert c["journal_admissible"] is False and not gt.eligible(c)


def test_pas_de_condition_probabilite_superieure_a_la_cote():
    c = cand(cote=1.30)   # réussite observée 70 % < 1/1,30 = 77 % : acceptée quand même
    assert c["probabilite_estimee"] < 1 / 1.30 and gt.eligible(c)


def test_le_journal_n_entre_jamais_dans_les_tickets_prudents():
    assert gt.eligible(cand(), "normal") and not gt.eligible(cand(), "prudent")


# --- classement : Wilson d'abord, sans ROI ------------------------------------------------------------------------------

def _pret(**kw):
    return cand(**kw)


@pytest.mark.parametrize("roi_a,roi_b", [(-0.9, 0.9), (0.0, 0.5), (5.0, -5.0)])
def test_roi_ne_change_pas_le_classement(roi_a, roi_b):
    assert gt.candidate_rank(_pret(roi=roi_a)) == gt.candidate_rank(_pret(roi=roi_b))


@pytest.mark.parametrize("fort,faible", [((10, 10), (8, 10)), ((20, 25), (4, 5)), ((9, 10), (9, 12))])
def test_classement_suit_la_borne_de_wilson(fort, faible):
    f = _pret(gagnes=fort[0], joues=fort[1], g6=6, j6=6)
    g = _pret(gagnes=faible[0], joues=faible[1], g6=6, j6=6)
    assert gt.candidate_rank(f) > gt.candidate_rank(g)
    assert not gt.candidate_rank(g) > gt.candidate_rank(f)


def test_non_admissible_passe_apres_les_admissibles():
    bon = _pret(gagnes=8, joues=10, cote=1.5, g6=5, j6=6)
    rejete = _pret(gagnes=10, joues=10, cote=2.5, g6=6, j6=6)
    assert gt.candidate_rank(bon) > gt.candidate_rank(rejete)


def test_classement_deterministe():
    rows = [_pret(gagnes=g, joues=j, equipe=f"E{g}{j}", g6=6, j6=6) for g, j in [(8, 10), (10, 10), (5, 6), (12, 15)]]
    a = sorted(rows, key=gt.candidate_rank, reverse=True)
    b = sorted(reversed(rows), key=gt.candidate_rank, reverse=True)
    assert [x["journal_team"] for x in a] == [x["journal_team"] for x in b]


# --- un pari par match, 15 au maximum, jamais complété --------------------------------------------------------------------

def test_un_pari_par_match_garde_le_mieux_classe():
    a = _pret(gagnes=10, joues=10, g6=6, j6=6)
    b = _pret(gagnes=8, joues=10, marche="Les deux équipes marquent")
    out = gt.un_pari_par_match_journal(sorted([a, b], key=gt.candidate_rank, reverse=True))
    assert len(out) == 1 and out[0]["journal_wins"] == 10


def test_matchs_differents_tous_gardes():
    rows = [_pret(adv=f"Adv{i}", equipe=f"Eq{i}") for i in range(4)]
    assert len(gt.un_pari_par_match_journal(rows)) == 4


def test_pas_de_remplissage_artificiel():
    rows = [_pret(adv=f"Adv{i}", equipe=f"Eq{i}") for i in range(3)] + \
           [_pret(adv=f"Hors{i}", equipe=f"Haut{i}", cote=2.6) for i in range(10)]
    assert len([x for x in gt.dedupe(rows) if gt.eligible(x)]) == 3


# --- mode, retour arrière, autres modes -----------------------------------------------------------------------------------

def test_mode_regularites_reconnu_et_wilson_reste_le_defaut(tmp_path):
    f = tmp_path / "c.json"
    f.write_text('{"mode": "regularites"}', encoding="utf-8")
    assert sa.journal_mode(f) == "regularites"
    f.write_text('{"mode": "nimportequoi"}', encoding="utf-8")
    assert sa.journal_mode(f) == "wilson"
    assert sa.journal_mode(tmp_path / "absent.json") == "wilson"


def test_les_autres_modes_ne_sont_pas_affectes():
    c = sa._journal_team_market_candidate(_ligne(cote=2.4), "wilson")
    assert c["probabilite_source"] == "JOURNAL_WILSON" and "journal_admissible" not in c
    assert c["journal_roi"] == 0.1 and not gt.journal_filtre(c)


def test_mode_regularites_ignore_les_paris_par_segment():
    journal = {"equipes_a_suivre": [], "segments": [{"x": 1}]}
    assert sa.extract_journal_candidates(journal, {"signaux": [{"date": "2099-01-01", "TOUS_MARCHES_EVALUES": [{}]}]},
                                         "regularites", STATS) == []


# --- suivi quotidien ------------------------------------------------------------------------------------------------------

def test_suivi_enregistre_sans_ecraser_les_resultats(tmp_path):
    f = tmp_path / "suivi.json"
    c = cand(cote=1.35)
    jrg.enregistre_suivi(f, "2026-10-10", [c])
    data = json.loads(f.read_text(encoding="utf-8"))
    assert len(data["jours"]["2026-10-10"]) == 1 and data["jours"]["2026-10-10"][0]["resultat"] is None
    data["jours"]["2026-10-10"][0]["resultat"] = 1
    f.write_text(json.dumps(data), encoding="utf-8")
    jrg.enregistre_suivi(f, "2026-10-10", [c])            # relance du même jour : le résultat est conservé
    again = json.loads(f.read_text(encoding="utf-8"))
    assert again["jours"]["2026-10-10"][0]["resultat"] == 1
    assert jrg.resume_suivi(again) == {"paris_resolus": 1, "reussis": 1, "reussite": 1.0}


def test_resume_suivi_vide():
    assert jrg.resume_suivi({})["reussite"] is None


# --- journal_rentabilite : 6 derniers matchs (ordre chronologique) ------------------------------------------------------

def _match(i, date, buts):
    return {"match_id": f"m{i}", "date": date, "ligue": "L", "domicile": "A", "exterieur": f"B{i}", "buts": buts, "cotes": {}}


def _lignes(resultats):
    """Équipe A à domicile 8 fois ; `resultats` = liste de (date, buts). Des matchs nuls ailleurs gardent le marché non banal."""
    matchs = [_match(i, d, b) for i, (d, b) in enumerate(resultats)]
    matchs += [{"match_id": f"f{i}", "date": f"2026-01-{(i % 28) + 1:02d}", "ligue": "L", "domicile": f"C{i}",
                "exterieur": f"D{i}", "buts": (0, 0), "cotes": {}} for i in range(40)]
    return [x for x in jr.construit_equipes_a_suivre(matchs, aujourdhui="2099-01-01", prochains={})
            if x["equipe"] == "A" and x["marche"] == "Victoire"]


def test_six_derniers_matchs_dans_l_ordre_chronologique():
    # 8 matchs : victoires les 6 premiers jours, défaites aux 2 derniers. Les 6 derniers = jours 3 à 8 -> 4 victoires.
    res = [(f"2026-09-{d:02d}", (2, 0) if d <= 6 else (0, 2)) for d in range(1, 9)]
    ligne = _lignes(list(reversed(res)))      # entrée volontairement dans le désordre
    assert len(ligne) == 1
    assert (ligne[0]["gagnes"], ligne[0]["joues"]) == (6, 8)
    assert (ligne[0]["gagnes_6"], ligne[0]["joues_6"]) == (4, 6)


@pytest.mark.parametrize("n_vict", [8, 7, 6])
def test_six_derniers_toutes_victoires_recentes(n_vict):
    res = [(f"2026-09-{d:02d}", (2, 0) if d > 8 - n_vict else (0, 2)) for d in range(1, 9)]
    ligne = _lignes(res)
    assert ligne and ligne[0]["gagnes_6"] == min(6, n_vict)


def test_moins_de_six_matchs_joues_6_egal_joues():
    res = [(f"2026-09-{d:02d}", (2, 0)) for d in range(1, 6)]
    ligne = _lignes(res)
    assert ligne and (ligne[0]["gagnes_6"], ligne[0]["joues_6"]) == (5, 5)


# --- résolution du suivi et accrochage dans le générateur ---------------------------------------------------------------

def _data_suivi(equipe="A", marche="Victoire", jour="2026-10-01", match="A - B1"):
    return {"jours": {jour: [{"match": match, "marche": marche, "equipe": equipe, "cote": 1.4, "resultat": None}]}}


@pytest.mark.parametrize("buts,attendu", [((2, 0), 1), ((3, 1), 1), ((0, 0), 0), ((0, 2), 0), ((1, 1), 0)])
def test_resout_suivi_victoire_a_domicile(buts, attendu):
    d = _data_suivi()
    matchs = [{"date": "2026-10-01", "domicile": "A", "exterieur": "B1", "buts": buts, "cotes": {}}]
    assert jrg.resout_suivi(d, matchs) == 1
    assert d["jours"]["2026-10-01"][0]["resultat"] == attendu


def test_resout_suivi_equipe_a_l_exterieur():
    d = _data_suivi(equipe="B1")
    matchs = [{"date": "2026-10-01", "domicile": "A", "exterieur": "B1", "buts": (0, 2), "cotes": {}}]
    assert jrg.resout_suivi(d, matchs) == 1 and d["jours"]["2026-10-01"][0]["resultat"] == 1


@pytest.mark.parametrize("d,matchs", [
    (_data_suivi(), []),                                                                         # match introuvable
    (_data_suivi(marche="Marché inconnu"), [{"date": "2026-10-01", "domicile": "A", "exterieur": "B1", "buts": (1, 0), "cotes": {}}]),
    (_data_suivi(jour="2026-10-02"), [{"date": "2026-10-01", "domicile": "A", "exterieur": "B1", "buts": (1, 0), "cotes": {}}]),
])
def test_resout_suivi_ne_devine_jamais(d, matchs):
    assert jrg.resout_suivi(d, matchs) == 0
    assert all(p["resultat"] is None for liste in d["jours"].values() for p in liste)


def test_suivi_regularites_sans_pari_du_mode_n_ecrit_rien(tmp_path):
    f = tmp_path / "s.json"
    assert gt.suivi_regularites({"pool": [{"probabilite_source": "JOURNAL_WILSON"}]}, f) is None
    assert not f.exists()


def test_suivi_regularites_ecrit_la_liste_du_jour(tmp_path):
    f = tmp_path / "s.json"
    c = gt.leg(cand(cote=1.35))
    c["date"] = "2099-10-10"
    out = gt.suivi_regularites({"pool": [c]}, f)
    assert out["erreur"] is None and f.exists()
    assert json.loads(f.read_text(encoding="utf-8"))["jours"]["2099-10-10"][0]["equipe"] == "Equipe Test"
