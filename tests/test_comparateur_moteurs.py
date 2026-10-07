import json
from pathlib import Path
import comparateur_moteurs as cm
def test_compare():
    v2=[{"match_id":"a","moteur_v2_6_10":{"selection":{"P1":{"marche":"1X2 - 1"}}}},{"match_id":"b","moteur_v2_6_10":{"selection":{"P1":{"marche":"BTTS - oui"}}}}]
    v3=[{"match_id":"a","moteur_v3":{"selection":{"P1":{"marche":"1X2 - 1"}}}},{"match_id":"b","moteur_v3":{"selection":{"P1":{"marche":"Over 2.5"}}}}]
    x=cm.compare(v2,v3); assert x["matchs_communs"]==2 and x["accord_marche"]==1 and x["divergence_marche"]==1
def test_main(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path); Path("data/v3").mkdir(parents=True)
    Path("precalcul_leger.json").write_text(json.dumps({"signaux":[{"match_id":"a","moteur_v2_6_10":{"selection":{"P1":{"marche":"1X2 - 1"}}}}]}))
    Path("data/v3/pronostics_v3.json").write_text(json.dumps({"signaux":[{"match_id":"a","moteur_v3":{"selection":{"P1":{"marche":"1X2 - 1"}}}}]}))
    assert cm.main()==0 and Path("data/comparaison_moteurs.json").exists()
