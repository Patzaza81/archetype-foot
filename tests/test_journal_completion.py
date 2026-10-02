from journal.journal_memoire import Historique
from journal.journal_sequences import analyser_sequences
from journal.journal_anticipation import anticiper
from journal.journal_persistance import evaluer_persistance
from journal.journal_validation import walk_forward

def h(i, result):
    return Historique(f"2026-09-{i:02d}", "A", "L", "BTTS - oui", "DOMICILE", result, 1.8)

def test_sequences_and_rupture():
    rows=[h(i, True) for i in range(1,7)] + [h(i, False) for i in range(7,12)]
    x=analyser_sequences(rows)
    assert x["serie_actuelle"]==5
    assert x["rupture"] is True

def test_anticipation_without_odds():
    x=anticiper({"regime":"RENFORCEMENT","niveau":"EXPLOITABLE","echantillon":10,"frequence":.7,"frequence_recente":.8,"tendance":.2})
    assert x["sans_cote"] is True
    assert x["prix"]=="EN_ATTENTE_DU_PRIX"

def test_persistence():
    rows=[h(i, i%2==0) for i in range(1,22)]
    x=evaluer_persistance(rows, signal_index=0)
    assert x["+1"]["disponible"] is True
    assert x["+20"]["disponible"] is True

def test_walk_forward_has_no_future_history():
    rows=[h(i, i%2==0) for i in range(1,12)]
    out=walk_forward(rows, min_history=5)
    assert out[0]["echantillon_avant"]==5
    assert out[0]["date_signal"]=="2026-09-06"


def test_reprise_requires_intermediate_break():
    rows=[h(i, True) for i in range(1,6)] + [h(i, False) for i in range(6,11)] + [h(i, True) for i in range(11,16)]
    x=analyser_sequences(rows)
    assert x["reprise"] is True
