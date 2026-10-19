"""Juges du super pronostic : chaque règle est testée sur 3 cas qui passent et 3 cas qui échouent."""
from matrice_scenarios import juges as J

SEUILS = {"q1_contrarien": 0.77, "q1_outsider": 0.85, "q99_ecart_cote": 0.17}


def cand(**k):
    base = {"j1": 0.9, "j4": 0.9, "valeur": 0.05, "cote": 1.5, "probabilite": 0.66, "p_calibree": 0.66, "ecart_cote": 0.0}
    base.update(k)
    return base


def juge(cands):
    J.juger_candidats(cands, SEUILS)
    return cands


def test_contrarien_passe():
    for j1 in (0.77, 0.9, 1.0):
        assert juge([cand(j1=j1)])[0]["juges"]["contrarien"]


def test_contrarien_echoue():
    for j1 in (0.0, 0.5, 0.76):
        assert not juge([cand(j1=j1)])[0]["juges"]["contrarien"]


def test_outsider_passe():
    for j4 in (0.85, 0.95, 1.0):
        assert juge([cand(j4=j4)])[0]["juges"]["outsider"]


def test_outsider_echoue():
    for j4 in (0.0, 0.6, 0.84):
        assert not juge([cand(j4=j4)])[0]["juges"]["outsider"]


def test_premiers_principes():
    for v in (0.01, 0.05, 0.3):
        assert juge([cand(valeur=v)])[0]["juges"]["premiers_principes"]
    for v in (0.0, -0.05, -0.4):
        assert not juge([cand(valeur=v)])[0]["juges"]["premiers_principes"]


def test_executant_cote_et_coherence():
    for c, e in ((1.26, 0.0), (1.5, 0.1), (3.0, 0.17)):
        assert juge([cand(cote=c, ecart_cote=e)])[0]["juges"]["executant"]
    for c, e in ((1.25, 0.0), (1.1, 0.0), (1.5, 0.3)):     # cote trop basse / cote incohérente avec la probabilité
        assert not juge([cand(cote=c, ecart_cote=e)])[0]["juges"]["executant"]


def test_expansionniste_domine():
    a, b = cand(probabilite=0.7, cote=1.6), cand(probabilite=0.6, cote=1.3)     # b est dominé par a (moins sûr ET moins payé)
    r = juge([a, b])
    assert r[0]["juges"]["expansionniste"] and not r[1]["juges"]["expansionniste"]


def test_dangereux_si_un_juge_cle_echoue():
    assert not juge([cand()])[0]["dangereux"]
    assert juge([cand(j1=0.1)])[0]["dangereux"]
    assert juge([cand(j4=0.1)])[0]["dangereux"]
    assert juge([cand(cote=1.1)])[0]["dangereux"]


def _p(cands, G, scen):
    for c in cands:
        c.setdefault("principal", False)
    J.juger_candidats(cands, {"q1_contrarien": 0, "q1_outsider": 0, "q99_ecart_cote": 1})
    return {"candidats": cands, "_G": G, "_scen": scen}


def test_super_marche_rien_si_aucun_ne_se_demarque():
    import numpy as np
    G = np.full((3, 3), 1 / 9)
    assert J.super_marche(_p([], G, {"nul": np.eye(3, dtype=bool)}), {"q1_contrarien": 0, "q1_outsider": 0}) is None


def test_super_marche_combine_meme_sens():
    import numpy as np
    G = np.zeros((4, 4)); G[0, 0] = .3; G[1, 0] = .3; G[0, 1] = .1; G[1, 1] = .1; G[2, 0] = .2
    i, j = np.meshgrid(range(4), range(4), indexing="ij")
    A = cand(groupe="double_chance", famille="double_chance", selection="1N", libelle="1N", cote=1.3, j1=1, j4=1, sure=1, dangereux=False, principal=False, _W=(i >= j))
    B = cand(groupe="over_under_2.5", famille="over_under", selection="moins", libelle="m2.5", cote=1.4, j1=1, j4=1, sure=1, dangereux=False, principal=False, _W=(i + j < 3))
    pr = cand(groupe="1x2", famille="1x2", selection="1", libelle="1", cote=1.28, j1=0.8, j4=0.8, sure=0.8, dangereux=False, principal=True, _W=(i > j))
    r = J.super_marche(_p([A, B, pr], G, {"nul": i == j}), {"q1_contrarien": 0, "q1_outsider": 0})
    assert r is None or r["type"] in ("combine", "simple")      # jamais le marché d'alpha tel quel
    assert not r or all(x["libelle"] != "1" for x in r["jambes"])


def test_super_marche_refuse_jambe_dangereuse():
    import numpy as np
    G = np.full((3, 3), 1 / 9)
    i, j = np.meshgrid(range(3), range(3), indexing="ij")
    A = cand(groupe="a", famille="a", selection="x", libelle="a", cote=1.1, sure=1, principal=False, _W=(i >= j))
    B = cand(groupe="b", famille="b", selection="x", libelle="b", cote=1.1, sure=1, principal=False, _W=(i + j < 3))
    assert J.super_marche(_p([A, B], G, {"nul": i == j}), {"q1_contrarien": 0, "q1_outsider": 0}) is None


def test_combine_reel_passe_avant_le_simple():
    import numpy as np
    G = np.full((3, 3), 1 / 9)
    i, j = np.meshgrid(range(3), range(3), indexing="ij")
    pr = cand(groupe="1x2", famille="1x2", selection="1", libelle="1", cote=1.3, j1=0.8, j4=0.8, principal=True, _W=(i > j))
    co = cand(groupe="dc_total_1.5", famille="combine", selection="1N|plus", libelle="DC+1,5", cote=1.96, j1=0.95, j4=0.95, principal=False, combine=True, valeur=0.2, _W=(i >= j))
    r = J.super_marche(_p([pr, co], G, {"nul": i == j}), {"q1_contrarien": 0, "q1_outsider": 0})
    assert r and r["type"] == "combine" and r["cote_combine"] == 1.96


def test_combine_moins_paye_que_le_principal_est_ecarte():
    import numpy as np
    G = np.full((3, 3), 1 / 9)
    i, j = np.meshgrid(range(3), range(3), indexing="ij")
    pr = cand(groupe="1x2", famille="1x2", selection="1", libelle="1", cote=2.0, j1=0.8, j4=0.8, principal=True, _W=(i > j))
    co = cand(groupe="dc_btts", famille="combine", selection="1N|Oui", libelle="x", cote=1.5, j1=0.95, j4=0.95, principal=False, combine=True, valeur=0.2, _W=(i >= j))
    assert J.super_marche(_p([pr, co], G, {"nul": i == j}), {"q1_contrarien": 0, "q1_outsider": 0}) is None


def test_combine_dangereux_est_ecarte():
    import numpy as np
    G = np.full((3, 3), 1 / 9)
    i, j = np.meshgrid(range(3), range(3), indexing="ij")
    pr = cand(groupe="1x2", famille="1x2", selection="1", libelle="1", cote=1.3, j1=0.8, j4=0.8, principal=True, _W=(i > j))
    co = cand(groupe="dc_btts", famille="combine", selection="1N|Oui", libelle="x", cote=3.0, j1=0.1, j4=0.95, principal=False, combine=True, valeur=0.2, _W=(i >= j))
    assert J.super_marche(_p([pr, co], G, {"nul": i == j}), {"q1_contrarien": 0.5, "q1_outsider": 0}) is None


P = {"domicile": "Alpha", "exterieur": "Beta", "series_buts": {"domicile": [(0, 1), (2, 0), (1, 1)], "exterieur": [(3, 2), (4, 1), (2, 2)]}}


def test_arguments_btts_non_cite_les_equipes_muettes():
    t = J._arguments({"groupe": "btts", "selection": "Non"}, P)
    assert "Alpha n'a pas marqué dans 1 de ses 3" in t and "Beta" not in t


def test_arguments_moins_de_buts_equipe_ne_cite_que_ce_qui_soutient():
    t = J._arguments({"groupe": "over_under_exterieur_1.5", "selection": "moins"}, P)
    assert "Alpha n'a encaissé que 2 buts" in t and "Beta" not in t         # Beta marque 9 en 3 matchs : n'appuie pas « moins »


def test_arguments_plus_de_buts_total():
    t = J._arguments({"groupe": "over_under_2.5", "selection": "plus"}, P)
    assert "Beta : 4,67" in t and "Alpha" not in t


def test_arguments_rien_si_rien_ne_soutient():
    assert J._arguments({"groupe": "over_under_domicile_0.5", "selection": "moins"}, P) == ""
    assert J._arguments({"groupe": "btts", "selection": "Oui"}, P).count("Beta") == 1
    assert J._arguments({"groupe": "btts", "selection": "Non"}, {**P, "series_buts": {"domicile": [(1, 0)], "exterieur": [(2, 2)]}}) == ""
