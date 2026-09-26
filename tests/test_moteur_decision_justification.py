from moteur_decision.justification_engine import require_justification

def row(gf,ga): return {"buts_marques":gf,"buts_encaisses":ga}

def test_missing_evidence_is_explicit():
    r=require_justification("btts_oui",[{}],[{}])
    assert r["code"]=="JUSTIFICATION_INSUFFISANTE"

def test_btts_can_be_supported_by_real_frequency():
    h=[row(1,0),row(2,1),row(1,1),row(2,0),row(1,2)]
    a=[row(1,0),row(1,1),row(2,0),row(1,2),row(2,1)]
    r=require_justification("btts_oui",h,a)
    assert r["code"]=="BTTS_SOUTENU_PAR_FREQUENCE_BUTS"
    assert r["facts"]


def test_justification_is_specific_to_total_line():
    h=[row(2,1),row(0,0),row(3,1),row(1,0),row(2,2)]
    a=[row(1,1),row(0,1),row(2,0),row(1,0),row(3,2)]
    r=require_justification("over_2_5",h,a)
    assert r["code"]=="TOTAL_LIGNE_SOUTENU_PAR_FREQUENCE_DIRECTE"
    assert "over_2_5" in r["facts"][0]

def test_exact_goals_requires_exact_historical_evidence():
    h=[row(2,0),row(1,1),row(3,0),row(0,0),row(4,1)]
    a=[row(1,1),row(0,1),row(2,0),row(1,0),row(3,2)]
    r=require_justification("exact_goals_2",h,a)
    assert r["code"]=="TOTAL_EXACT_SOUTENU_PAR_FREQUENCE"
    assert "total exact sélectionné" in r["facts"][0]

def test_second_half_justification_is_not_fabricated_without_second_half_data():
    h=[row(1,0)]
    a=[row(1,0)]
    r=require_justification("2e_mi_temps_btts_oui",h,a)
    assert r["code"]=="JUSTIFICATION_INSUFFISANTE"
