"""Tests du mode « regularites » du Journal : sans ROI, plafond de cote, un pari par match, 15 maximum.

Règle du dépôt : fonctions de comparaison testées sur au moins 3 cas qui passent et 3 qui échouent.
"""
import pytest

import generateur_tickets as gt
import selection_adaptative as sa


def _ligne(cote=1.60, gagnes=8, joues=10, roi=0.1, adv="Adv", equipe="Equipe Test", marche="Match à moins de 3,5 buts"):
    return {"equipe": equipe, "ligue": "Ligue Test", "marche": marche, "gagnes": gagnes, "joues": joues,
            "frequence": gagnes / joues, "frequence_generale": 0.5, "roi_betpawa": roi,
            "prochain_match": {"date": "2099-10-10", "heure": "15:00", "adversaire": adv, "lieu": "domicile",
                               "cote_betpawa": cote, "betpawa_url": "https://example.invalid/e"}}


def _cand(**kw):
    c = sa._journal_team_market_candidate(_ligne(**kw), "regularites")
    return c


def _pret(**kw):
    """Candidat tel que le générateur le reçoit (après enrich n'est pas nécessaire : champs du Journal suffisent)."""
    c = _cand(**kw)
    c["probabilite"] = c["probabilite_estimee"]
    return c


# --- plafond de cote : 3 cas admissibles, 3 rejetés ---------------------------------------------------------------------

@pytest.mark.parametrize("cote", [1.30, 1.55, 1.80])
def test_regularites_admissible_sous_le_plafond(cote):
    c = _cand(cote=cote)
    assert c["journal_admissible"] is True
    assert c["probabilite_source"] == "JOURNAL_REGULARITE"
    assert gt.eligible(_pret(cote=cote))


@pytest.mark.parametrize("cote", [1.81, 2.30, 3.00])
def test_regularites_rejete_au_dessus_du_plafond(cote):
    c = _cand(cote=cote)
    assert c["journal_admissible"] is False
    assert c["journal_motifs_rejet"] == ["COTE_AU_DESSUS_DU_PLAFOND"]
    assert not gt.eligible(_pret(cote=cote))


def test_regularites_ne_demande_pas_proba_superieure_a_la_cote():
    """Wilson 8/10 = 49 % < 1/1,6 = 62,5 % : la règle actuelle (Wilson >= 1/cote) le rejette, le mode regularites l'accepte."""
    assert _cand()["probabilite_estimee"] < 1 / 1.60
    assert gt.eligible(_pret())


# --- ROI absent du classement : 3 cas où le ROI change sans changer l'ordre, 3 cas où l'ordre suit Wilson/volume --------

@pytest.mark.parametrize("roi_a,roi_b", [(-0.9, 0.9), (0.0, 0.5), (5.0, -5.0)])
def test_roi_ne_change_pas_le_classement(roi_a, roi_b):
    a, b = _pret(roi=roi_a), _pret(roi=roi_b)
    assert gt.candidate_rank(a) == gt.candidate_rank(b)


@pytest.mark.parametrize("fort,faible", [((10, 10), (8, 10)), ((20, 25), (4, 5)), ((9, 10), (9, 12))])
def test_classement_suit_la_borne_de_wilson(fort, faible):
    f, g = _pret(gagnes=fort[0], joues=fort[1]), _pret(gagnes=faible[0], joues=faible[1])
    assert gt.candidate_rank(f) > gt.candidate_rank(g)


@pytest.mark.parametrize("fort,faible", [((10, 10), (8, 10)), ((20, 25), (4, 5)), ((9, 10), (9, 12))])
def test_classement_ne_prefere_pas_le_plus_faible(fort, faible):
    f, g = _pret(gagnes=fort[0], joues=fort[1]), _pret(gagnes=faible[0], joues=faible[1])
    assert not gt.candidate_rank(g) > gt.candidate_rank(f)


def test_non_admissible_passe_apres_tous_les_admissibles():
    bon = _pret(gagnes=5, joues=10, cote=1.5)
    rejete = _pret(gagnes=10, joues=10, cote=2.5)
    assert gt.candidate_rank(bon) > gt.candidate_rank(rejete)


def test_classement_deterministe():
    rows = [_pret(gagnes=g, joues=j, equipe=f"E{g}{j}") for g, j in [(8, 10), (10, 10), (5, 6), (12, 15)]]
    a = sorted(rows, key=gt.candidate_rank, reverse=True)
    b = sorted(reversed(rows), key=gt.candidate_rank, reverse=True)
    assert [x["journal_team"] for x in a] == [x["journal_team"] for x in b]


# --- un pari par match, 15 maximum, jamais complété ----------------------------------------------------------------------

def test_un_pari_par_match_garde_le_mieux_classe():
    a, b = _pret(gagnes=10, joues=10), _pret(gagnes=8, joues=10, marche="Les deux équipes marquent")
    out = gt.un_pari_par_match_journal(sorted([a, b], key=gt.candidate_rank, reverse=True))
    assert len(out) == 1 and out[0]["journal_wins"] == 10


def test_matchs_differents_sont_tous_gardes():
    rows = [_pret(adv=f"Adv{i}", equipe=f"Eq{i}") for i in range(4)]
    assert len(gt.un_pari_par_match_journal(rows)) == 4


def test_pas_de_remplissage_artificiel():
    data = {"journal": [_pret(adv=f"Adv{i}", equipe=f"Eq{i}") for i in range(3)] +
                       [_pret(adv=f"Hors{i}", equipe=f"Haut{i}", cote=2.6) for i in range(10)]}
    rows = [x for x in gt.dedupe(data["journal"]) if gt.eligible(x)]
    assert len(rows) == 3


# --- mode et retour arrière ------------------------------------------------------------------------------------------------

def test_mode_regularites_est_reconnu_et_wilson_reste_le_defaut(tmp_path):
    f = tmp_path / "c.json"
    f.write_text('{"mode": "regularites"}', encoding="utf-8")
    assert sa.journal_mode(f) == "regularites"
    f.write_text('{"mode": "nimportequoi"}', encoding="utf-8")
    assert sa.journal_mode(f) == "wilson"
    assert sa.journal_mode(tmp_path / "absent.json") == "wilson"


def test_les_autres_modes_ne_sont_pas_affectes():
    c = sa._journal_team_market_candidate(_ligne(cote=2.4), "wilson")
    assert c["probabilite_source"] == "JOURNAL_WILSON" and "journal_admissible" not in c
    assert not gt.journal_filtre(c)
