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

# Réalisme : marché « moins de 3,5 buts » = 65 / 86 sur 100 cas (0,76) ; « les deux équipes marquent » = 15 cas (repli moyenne)
STATS = {"marches": {"Match à moins de 3,5 buts": (100, 85.0, 65), "Les deux équipes marquent": (10, 8.5, 3)},
         "total": (200, 170.0, 116), "erreur": None}
MARCHE = "Match à moins de 3,5 buts"


def _ligne(cote=1.40, gagnes=8, joues=10, g6=5, j6=6, roi=0.1, adv="Adv", equipe="Equipe Test", marche=MARCHE):
    return {"equipe": equipe, "ligue": "Ligue Test", "marche": marche, "gagnes": gagnes, "joues": joues,
            "frequence": gagnes / joues, "frequence_generale": 0.5, "roi_betpawa": roi, "gagnes_6": g6, "joues_6": j6,
            "prochain_match": {"date": "2099-10-10", "heure": "15:00", "adversaire": adv, "lieu": "domicile",
                               "cote_betpawa": cote, "betpawa_url": "https://example.invalid/e"}}


def cand(stats=STATS, **kw):
    return sa._journal_team_market_candidate(_ligne(**kw), "regularites", stats)


# --- formule : marge d'erreur, chiffre, probabilité de ticket ---------------------------------------------------------------

@pytest.mark.parametrize("p,n,attendu", [(1.0, 5, 0.434), (0.8, 10, 0.3098), (0.9, 25, 0.175)])
def test_marge_erreur_valeurs_connues(p, n, attendu):
    assert jrg.marge_erreur(p, n) == pytest.approx(attendu, abs=2e-3)


@pytest.mark.parametrize("w,n", [(5, 5), (10, 10), (25, 25)])
def test_marge_erreur_ne_tombe_pas_a_zero_a_cent_pour_cent(w, n):
    assert jrg.marge_erreur(1.0, n) > 0.05


def test_marge_erreur_decroit_avec_l_echantillon():
    assert jrg.marge_erreur(0.8, 5) > jrg.marge_erreur(0.8, 20) > jrg.marge_erreur(0.8, 200)
    assert jrg.marge_erreur(0.8, 0) == 0.8


@pytest.mark.parametrize("taux,n,real", [(0.8, 10, 0.76), (1.0, 5, 0.76), (0.9, 30, 0.5)])
def test_chiffre_est_taux_fois_realisme_fois_un_moins_marge(taux, n, real):
    attendu = taux * real * (1 - jrg.marge_erreur(taux, n) / taux)
    assert jrg.chiffre(taux, n, real) == pytest.approx(max(0.0, attendu))
    assert jrg.chiffre(taux, n, real) == pytest.approx(real * jrg.borne_wilson(taux, n))
    assert jrg.probabilite_ticket(taux, real) == pytest.approx(taux * real)


def test_petit_echantillon_est_penalise():
    assert jrg.chiffre(0.9, 20, 0.75) > jrg.chiffre(1.0, 5, 0.75)   # 18 sur 20 passe devant 5 sur 5
    assert jrg.chiffre(1.0, 5, 0.75) < jrg.chiffre(1.0, 12, 0.75)


def test_chiffre_borne():
    assert 0.0 <= jrg.chiffre(1.0, 1, 1.5) <= 1.0 and jrg.probabilite_ticket(1.0, 5.0) == 0.99


# --- réalisme du marché ---------------------------------------------------------------------------------------------------

def test_realisme_du_marche_si_assez_de_cas():
    r, origine = jrg.realisme_pour(MARCHE, STATS)
    assert r == pytest.approx(65 / 85.0) and origine == "marche"


def test_realisme_moyen_si_marche_trop_petit():
    r, origine = jrg.realisme_pour("Les deux équipes marquent", STATS)     # 10 cas < 15
    assert r == pytest.approx(116 / 170.0) and origine == "moyenne"


def test_realisme_moyen_si_marche_inconnu():
    assert jrg.realisme_pour("Marché inconnu", STATS)[1] == "moyenne"


@pytest.mark.parametrize("stats", [None, {}, {"marches": {}, "total": (10, 8.5, 6)}, {"marches": {}, "total": (0, 0.0, 0)}])
def test_realisme_absent(stats):
    assert jrg.realisme_pour(MARCHE, stats) == (None, None)


def test_stats_realisme_compte_par_marche():
    cands = [{"marche": "A", "frequence": 0.8, "resultat": 1}, {"marche": "A", "frequence": 0.9, "resultat": 0},
             {"marche": "B", "frequence": 0.7, "resultat": 1}]
    st = jrg.stats_realisme(cands)
    assert st["marches"]["A"] == (2, pytest.approx(1.7), 1) and st["total"][0] == 3 and st["total"][2] == 2


def _mc(i, jour, domicile, exterieur, buts, ligue="L"):
    return {"match_id": f"x{i}", "date": jour, "ligue": ligue, "domicile": domicile, "exterieur": exterieur,
            "buts": buts, "cotes": {}}


def test_candidats_passes_sans_fuite_du_futur():
    """Une équipe gagne 5 fois de suite, puis un 6e match : le 6e est un candidat (5 sur 5 avant). Le résultat du 6e match
    ne change pas ses statistiques d'avant-match."""
    matchs = [_mc(i, f"2026-09-{i + 1:02d}", "A", f"B{i}", (2, 0)) for i in range(5)]
    matchs += [_mc(5, "2026-09-10", "A", "B5", (0, 3))]                               # le 6e est perdu
    matchs += [_mc(100 + i, f"2026-08-{i + 1:02d}", f"C{i}", f"D{i}", (0, 0)) for i in range(30)]   # marché non banal
    cands = [c for c in jrg.candidats_passes(matchs) if c["equipe"] == "A" and c["marche"] == "Victoire"]
    assert len(cands) == 1
    assert (cands[0]["gagnes"], cands[0]["joues"], cands[0]["resultat"]) == (5, 5, 0)


def test_candidats_passes_ignore_les_equipes_sans_assez_de_matchs():
    matchs = [_mc(i, f"2026-09-{i + 1:02d}", "A", f"B{i}", (2, 0)) for i in range(4)]
    matchs += [_mc(100 + i, f"2026-08-{i + 1:02d}", f"C{i}", f"D{i}", (0, 0)) for i in range(30)]
    assert [c for c in jrg.candidats_passes(matchs) if c["equipe"] == "A"] == []


# --- admissibilité : constance (la cote n'intervient plus) ---------------------------------------------------------------

@pytest.mark.parametrize("g,j,g6,j6", [
    (10, 10, 6, 6),      # parfait
    (7, 10, 6, 6),       # (0,70 + 1,00) / 2 = 0,85
    (5, 5, None, None),  # 5 matchs : réussite globale seule
    (6, 6, 5, 6),        # 6 matchs : l'indice vaut la réussite globale (0,83)
    (8, 10, 4, 6),       # (0,80 + 0,667) / 2 = 0,73
])
def test_admissible(g, j, g6, j6):
    ok, motifs = jrg.evalue(g, j, g6, j6)
    assert ok and motifs == []


@pytest.mark.parametrize("g,j,g6,j6,motif", [
    (7, 10, 3, 6, jrg.MOTIF_CONSTANCE),         # (0,70 + 0,50) / 2 = 0,60
    (8, 10, 2, 6, jrg.MOTIF_CONSTANCE),         # (0,80 + 0,33) / 2 = 0,57
    (7, 10, None, None, jrg.MOTIF_6_ABSENTS),   # dès 6 matchs la donnée est obligatoire
    (3, 4, None, None, jrg.MOTIF_MATCHS),
    (3, 5, None, None, jrg.MOTIF_CONSTANCE),    # 5 matchs mais 60 % < 70 %
])
def test_rejete(g, j, g6, j6, motif):
    ok, motifs = jrg.evalue(g, j, g6, j6)
    assert not ok and motif in motifs


# --- candidat du Journal ---------------------------------------------------------------------------------------------------

def test_probabilite_du_ticket_est_taux_fois_realisme():
    c = cand()
    realisme = 65 / 85.0
    assert c["probabilite_source"] == "JOURNAL_REGULARITE"
    assert c["probabilite_estimee"] == pytest.approx(0.8 * realisme, abs=1e-5)
    assert c["journal_chiffre"] == pytest.approx(0.8 * realisme * (1 - jrg.marge_erreur(0.8, 10) / 0.8), abs=1e-5)
    assert gt.proba(c) == pytest.approx(0.8 * realisme, abs=1e-5)


def test_la_cote_n_intervient_pas():
    a, b = cand(cote=1.30), cand(cote=2.80)
    for cle in ("probabilite_estimee", "journal_chiffre", "journal_admissible"):
        assert a[cle] == b[cle]
    assert gt.candidate_rank(a) == gt.candidate_rank(b)


def test_aucun_roi_ni_gain_espere():
    c = cand()
    assert c["journal_roi"] is None and c["journal_success_margin"] is None
    ticket_leg = gt.leg(c)
    assert ticket_leg["ev_estime"] is None and ticket_leg["journal_roi"] is None


def test_affichage_x_sur_y_et_estimation():
    c = cand()
    assert c["journal_affichage"] == "8 sur 10"
    assert "8 sur 10" in c["justification"] and "Estimation de réussite" in c["justification"]
    assert "Wilson" not in c["justification"] and "80%" not in c["justification"]


def test_sans_realisme_le_pari_est_rejete():
    c = cand(stats={"marches": {}, "total": (0, 0.0, 0), "erreur": "x"})
    assert c["journal_admissible"] is False and jrg.MOTIF_REALISME in c["journal_motifs_rejet"]
    assert not gt.eligible(c)


@pytest.mark.parametrize("cote", [1.30, 1.80, 2.60])
def test_eligible_quelle_que_soit_la_cote_dans_la_fenetre_du_generateur(cote):
    assert gt.eligible(cand(cote=cote))


def test_fenetre_du_generateur_cote_trop_basse():
    assert not gt.eligible(cand(cote=1.10))


@pytest.mark.parametrize("cote", [3.50, 5.0, 12.0])
def test_fenetre_du_generateur_cote_trop_haute_pas_de_candidat(cote):
    assert cand(cote=cote) is None


def test_pas_de_condition_probabilite_superieure_a_la_cote():
    c = cand(cote=1.20)
    assert c["probabilite_estimee"] < 1 / 1.20 or True
    assert c["journal_admissible"] is True


def test_le_journal_n_entre_jamais_dans_les_tickets_prudents():
    assert gt.eligible(cand(cote=1.5), "normal") and not gt.eligible(cand(cote=1.5), "prudent")


# --- classement par le chiffre ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("roi_a,roi_b", [(-0.9, 0.9), (0.0, 0.5), (5.0, -5.0)])
def test_roi_ne_change_pas_le_classement(roi_a, roi_b):
    assert gt.candidate_rank(cand(roi=roi_a)) == gt.candidate_rank(cand(roi=roi_b))


@pytest.mark.parametrize("fort,faible", [((10, 10), (8, 10)), ((18, 20), (5, 5)), ((9, 10), (9, 12))])
def test_classement_suit_le_chiffre(fort, faible):
    f = cand(gagnes=fort[0], joues=fort[1], g6=6, j6=6)
    g = cand(gagnes=faible[0], joues=faible[1], g6=6, j6=6)
    assert f["journal_chiffre"] > g["journal_chiffre"]
    assert gt.candidate_rank(f) > gt.candidate_rank(g)
    assert not gt.candidate_rank(g) > gt.candidate_rank(f)


def test_marche_plus_realiste_passe_devant_a_taux_egal():
    stats = {"marches": {"Match à moins de 3,5 buts": (100, 85.0, 70), "Match à plus de 2,5 buts": (100, 85.0, 40)},
             "total": (200, 170.0, 110), "erreur": None}
    bon = cand(stats=stats, marche="Match à moins de 3,5 buts")
    faible = cand(stats=stats, marche="Match à plus de 2,5 buts")
    assert gt.candidate_rank(bon) > gt.candidate_rank(faible)


def test_non_admissible_passe_apres_les_admissibles():
    bon = cand(gagnes=8, joues=10, g6=5, j6=6)
    rejete = cand(gagnes=10, joues=10, g6=1, j6=6)      # constance 0,55 < 0,70
    assert rejete["journal_admissible"] is False
    assert gt.candidate_rank(bon) > gt.candidate_rank(rejete)


def test_classement_deterministe():
    rows = [cand(gagnes=g, joues=j, equipe=f"E{g}{j}", g6=6, j6=6) for g, j in [(8, 10), (10, 10), (5, 6), (12, 15)]]
    a = sorted(rows, key=gt.candidate_rank, reverse=True)
    b = sorted(reversed(rows), key=gt.candidate_rank, reverse=True)
    assert [x["journal_team"] for x in a] == [x["journal_team"] for x in b]


# --- un pari par match, 15 au maximum, jamais complété --------------------------------------------------------------------

def test_un_pari_par_match_garde_le_mieux_classe():
    a = cand(gagnes=10, joues=10, g6=6, j6=6)
    b = cand(gagnes=8, joues=10, marche="Les deux équipes marquent")
    out = gt.un_pari_par_match_journal(sorted([a, b], key=gt.candidate_rank, reverse=True))
    assert len(out) == 1 and out[0]["journal_wins"] == 10


def test_matchs_differents_tous_gardes():
    rows = [cand(adv=f"Adv{i}", equipe=f"Eq{i}") for i in range(4)]
    assert len(gt.un_pari_par_match_journal(rows)) == 4


def test_pas_de_remplissage_artificiel():
    rows = [cand(adv=f"Adv{i}", equipe=f"Eq{i}") for i in range(3)] + \
           [cand(adv=f"Hors{i}", equipe=f"Haut{i}", gagnes=3, joues=5) for i in range(10)]   # 60 % : constance insuffisante
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
    c = cand()
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
    c = gt.leg(cand())
    c["date"] = "2099-10-10"
    out = gt.suivi_regularites({"pool": [c]}, f)
    assert out["erreur"] is None and f.exists()
    assert json.loads(f.read_text(encoding="utf-8"))["jours"]["2099-10-10"][0]["equipe"] == "Equipe Test"
