import copy

from moteur_v2r import echantillon as X, integration as I, regles as R, sensibilite as S
from moteur_v2r.donnees import charge

MS = [m for m in charge() if m["h"] is not None]
JOURS = ["2026-10-13"]


def test_decrit_compte_les_matchs():
    d = S.decrit(MS)
    assert d["matchs"] == len(MS) and d["du"] <= d["au"] and sum(n for _, n in d["par_jour"]) == len(MS)


def test_configuration_restauree_apres_essai():
    avant = (copy.deepcopy(R.CONFIG), X.PAS_COTE, I.COUPURES_LIGUE, I.COUPURES_MATCH)
    S.rejoue_avec(MS, JOURS, min_paris=5, roi_min=0.1, pas=0.5, coupures_ligue=(2.0, 3.0), coupures_match=(2.0, 3.5))
    assert (R.CONFIG, X.PAS_COTE, I.COUPURES_LIGUE, I.COUPURES_MATCH) == avant


def test_configuration_restauree_meme_en_cas_d_erreur():
    avant = copy.deepcopy(R.CONFIG)
    try:
        S.rejoue_avec([{"cassé": 1}], JOURS, min_paris=3)
    except Exception:  # noqa: BLE001
        pass
    assert R.CONFIG == avant


def test_seuil_impossible_donne_zero_pari():
    assert S.rejoue_avec(MS, JOURS, min_paris=10 ** 6)["paris"] == 0


def test_roi_min_impossible_donne_zero_pari():
    assert S.rejoue_avec(MS, JOURS, roi_min=1e9)["paris"] == 0


def test_base_identique_a_backtest():
    from moteur_v2r import backtest as B
    assert S.rejoue_avec(MS, JOURS)["paris"] == B.resume(B.rejoue(MS, JOURS)["v2r"])["paris"]


def test_parametre_plus_permissif_donne_plus_de_paris():
    assert S.rejoue_avec(MS, JOURS, roi_min=0.0)["paris"] >= S.rejoue_avec(MS, JOURS)["paris"]
