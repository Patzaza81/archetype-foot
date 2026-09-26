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
