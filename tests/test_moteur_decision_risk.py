from moteur_decision.risk_engine import assess_dispersion, coefficient_of_variation, exposure_group
from moteur_decision.decision_engine import decide

def test_dispersion_rules():
    assert assess_dispersion([1,1,1,1],.70).eligible
    assert assess_dispersion([1,2,1,2],.66).eligible is False
    assert assess_dispersion([0.1,3,0.2,4],.80).eligible is False

def test_exposure_groups():
    assert exposure_group("btts_oui")=="btts_ft"
    assert exposure_group("over_2_5")=="buts_total_ft"
    assert exposure_group("handicap_3way_1_dom")=="handicap_ft"
    assert exposure_group("mi_temps_victoire")=="resultat_mi_temps"
    assert exposure_group("2e_mi_temps_dc_X2")=="double_chance_2e_mi_temps"

def test_decision_never_fabricates_justification():
    cs=[{"market":"x","probability":.75,"odds":1.5,"edge":.08,"edv":12,"eligible":True}]
    assert decide(cs)==[]

def test_decision_is_adaptive_and_capped():
    cs=[
      {"market":"btts_oui","probability":.70,"odds":1.6,"edge":.075,"edv":12,"eligible":True,"justification_code":"DATA_BTTS"},
      {"market":"over_2_5","probability":.69,"odds":1.6,"edge":.065,"edv":10.4,"eligible":True,"justification_code":"DATA_TOTAL"},
      {"market":"clean_sheet_dom","probability":.64,"odds":1.7,"edge":.052,"edv":8.84,"eligible":True,"justification_code":"DATA_CS"},
      {"market":"victoire","probability":.75,"odds":1.6,"edge":.125,"edv":20,"eligible":True,"justification_code":"DATA_1X2"},
    ]
    out=decide(cs,max_selections=3)
    assert len(out)==3
    assert out[0].market=="victoire"
    assert all(x.action=="SELECTION_SEPAREE" for x in out)

def test_explicit_conflict_is_respected():
    cs=[
      {"market":"btts_oui","probability":.70,"odds":1.6,"edge":.075,"edv":12,"eligible":True,"justification_code":"A"},
      {"market":"over_2_5","probability":.69,"odds":1.6,"edge":.065,"edv":10.4,"eligible":True,"justification_code":"B",
       "conflicts_with":["btts_oui"]},
      {"market":"clean_sheet_dom","probability":.64,"odds":1.7,"edge":.052,"edv":8.84,"eligible":True,"justification_code":"C"},
    ]
    out=decide(cs,max_selections=3)
    assert {x.market for x in out}=={"btts_oui","clean_sheet_dom"}
