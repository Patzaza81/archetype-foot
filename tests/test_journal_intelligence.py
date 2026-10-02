from journal.journal_memoire import Historique, construire_historique, evaluer_marche, resolve
from journal.journal_regimes import regime
from journal.journal_cotes import tranche_cote

def h(i, res, team="A", ctx="DOMICILE", comp="L", market="BTTS - oui", cote=1.8):
    return Historique(f"2026-09-{i:02d}", team, comp, market, ctx, res, cote)

def test_no_future_leakage():
    rows=[
        {"date":"2026-09-01","domicile":"A","exterieur":"B","competition":"L","cotes_observees":{"BTTS - oui":1.8},"score":{"buts_dom":1,"buts_ext":1}},
        {"date":"2026-09-10","domicile":"A","exterieur":"C","competition":"L","cotes_observees":{"BTTS - oui":1.8},"score":{"buts_dom":0,"buts_ext":0}},
    ]
    out=construire_historique(rows,"2026-09-05")
    assert len(out)==2
    assert all(x.date < "2026-09-05" for x in out)

def test_hierarchical_fallback():
    rows=[h(i,True) for i in range(1,4)]+[h(i,False) for i in range(4,8)]
    level,sample=resolve(rows,"A","BTTS - oui","L","DOMICILE",min_exact=3)
    assert level=="equipe+marche+competition+contexte"
    assert len(sample)==7

def test_fallback_drops_to_team_market():
    rows=[h(i,True,ctx="EXTERIEUR",comp="OTHER") for i in range(1,4)]
    level,sample=resolve(rows,"A","BTTS - oui","L","DOMICILE",min_exact=3)
    assert level=="equipe+marche"
    assert len(sample)==3

def test_regime_is_transparent_and_windowed():
    rows=[h(i,True) for i in range(1,9)]
    result=regime(rows)
    assert result["frequence"]==1.0
    assert result["frequence_recente"]==1.0
    assert result["regime"] in {"PERSISTANT","RENFORCEMENT"}
    assert "score" not in result

def test_market_evaluation():
    assert evaluer_marche("BTTS - oui",1,1) is True
    assert evaluer_marche("Plus de 2.5 buts",2,1) is True
    assert evaluer_marche("Moins de 2.5 buts",1,1) is True
    assert evaluer_marche("1X2 - 1",2,1) is True

def test_price_bands_are_disjoint():
    assert tranche_cote(1.29)=="<1.30"
    assert tranche_cote(1.30)=="1.30-1.49"
    assert tranche_cote(1.50)=="1.50-1.74"
    assert tranche_cote(2.00)=="2.00-2.49"
    assert tranche_cote(3.00)=="3.00+"


def test_n1_snapshot_reader(tmp_path):
    from journal.journal_n1 import charger_n1, stats_equipe_marche
    snap=tmp_path/"2526"/"raw"
    snap.mkdir(parents=True)
    (tmp_path/"2526"/"_SNAPSHOT_COMPLETE.json").write_text("{}",encoding="utf-8")
    (snap/"E0.csv").write_text("Date,HomeTeam,AwayTeam,FTHG,FTAG\n01/01/26,Alpha,Beta,2,1\n",encoding="utf-8")
    rows=charger_n1(str(tmp_path))
    result=stats_equipe_marche(rows,"Alpha","1X2 - 1","DOMICILE")
    assert result["disponible"] is True
    assert result["echantillon"]==1
    assert result["frequence"]==1.0
