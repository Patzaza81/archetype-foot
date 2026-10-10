import itertools
import pytest
from moteur_v3.markets import gagne
from moteur_v3.performance import marge
from v2_indice import marche_v3, indice_du_marche, ajoute_indices


def v2_gagne(mk, h, a):
    """Règlement du marché V2, écrit indépendamment du mapping."""
    d = h - a
    t = {"victoire": d > 0, "defaite": d < 0, "dc_1X": d >= 0, "dc_X2": d <= 0, "dc_12": d != 0,
         "btts_oui": h > 0 and a > 0, "btts_non": h == 0 or a == 0, "clean_sheet_dom": a == 0, "clean_sheet_ext": h == 0,
         "over_2_5": h + a > 2.5, "under_3_5": h + a < 3.5,
         "buts_dom_over_1_5": h > 1.5, "buts_ext_under_0_5": a < 0.5,
         "handicap_dom_-1_5": d - 1.5 > 0, "handicap_dom_+1_5": d + 1.5 > 0, "handicap_dom_+0_5": d + 0.5 > 0,
         "handicap_ext_+1_5": a + 1.5 > h, "handicap_ext_-0_5": a - 0.5 > h, "handicap_ext_+0_5": a + 0.5 > h,
         "handicap_dom_-0_5": d - 0.5 > 0, "handicap_ext_-1_5": a - 1.5 > h}
    return t[mk]


@pytest.mark.parametrize("mk", ["victoire", "defaite", "dc_1X", "dc_X2", "dc_12", "btts_oui", "btts_non", "clean_sheet_dom",
                                "clean_sheet_ext", "over_2_5", "under_3_5", "buts_dom_over_1_5", "buts_ext_under_0_5",
                                "handicap_dom_-1_5", "handicap_dom_+1_5", "handicap_dom_+0_5", "handicap_ext_+1_5",
                                "handicap_ext_-0_5", "handicap_ext_+0_5", "handicap_dom_-0_5", "handicap_ext_-1_5"])
def test_mapping_meme_reglement_que_v2(mk):
    m3 = marche_v3(mk)
    assert m3 is not None
    for h, a in itertools.product(range(7), range(7)):
        assert (marge(m3, h, a) > 0) == v2_gagne(mk, h, a), (mk, m3, h, a)


@pytest.mark.parametrize("mk", ["nul", "inconnu", "handicap_dom_x", "over_2", ""])
def test_sans_indice(mk):
    assert marche_v3(mk) is None


def _m(gf, ga):
    return {"buts_marques": gf, "buts_encaisses": ga, "date": "2026-01-01", "domicile": True}


def test_ajoute_indices_sans_toucher_le_reste():
    dom = [dict(_m(2, 0), date=f"2026-0{i}-01", domicile=True) for i in range(1, 6)]
    ext = [dict(_m(0, 2), date=f"2026-0{i}-01", domicile=False) for i in range(1, 6)]
    s = {"match_id": "x", "moteur_v2_6_10": {
        "selection": {"P1": {"marche_moteur": "victoire", "probabilite": 0.5}, "P2": None},
        "inventaire": [{"marche_moteur": "nul", "probabilite": 0.2}, {"marche_moteur": "dc_1X", "probabilite": 0.7}]}}
    n = ajoute_indices([s], {"x": {"equipe_dom": {"matchs": dom}, "equipe_ext": {"matchs": ext}}})
    b = s["moteur_v2_6_10"]
    assert n == 2 and b["selection"]["P1"]["indice_performance"]["indice"] == 4
    assert "indice_performance" not in b["inventaire"][0] and b["selection"]["P1"]["probabilite"] == 0.5
    assert ajoute_indices([{"match_id": "zz", "moteur_v2_6_10": {}}], {}) == 0
