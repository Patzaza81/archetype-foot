"""A4 (24/09/2026) : contrôle qualité Football-Data. Cas qui doivent être comptés comme accords, et cas qui doivent
être signalés (désaccord, doublon, date future) ou exclus (équipe non reliée, date trop éloignée)."""
import datetime

import controle_football_data as cf

D = datetime.date
CORR = {"divisions": {"E1": {"equipes": {"Norwich": {"matchendirect": "Norwich City"},
                                         "Leeds": {"matchendirect": "Leeds"},
                                         "Hull": {"matchendirect": "Hull City"}}}}}


def fd(date, dom, ext, h, a):
    return {"competition_code": "E1", "date": date, "home_team": dom, "away_team": ext,
            "full_time_home_goals": h, "full_time_away_goals": a}


def med(date, dom, ext, h, a):
    return {"date": D.fromisoformat(date), "domicile": dom, "exterieur": ext, "competition": "x", "buts": (h, a)}


def run(fds, meds):
    return cf.controle(fds, meds, CORR, aujourd_hui=D(2026, 9, 24))


# --- doivent être comptés comme accords -------------------------------------------------------------------------------
def test_meme_score_meme_date_accord():
    r = run([fd("2026-09-20", "Norwich", "Leeds", 2, 1)], [med("2026-09-20", "Norwich City", "Leeds", 2, 1)])
    assert r["resume"]["accords"] == 1 and r["resume"]["taux_accord"] == 1.0 and r["resume"]["critere_atteint"]


def test_date_decalee_d_un_jour_appariee():
    r = run([fd("2026-09-20", "Norwich", "Leeds", 2, 1)], [med("2026-09-21", "Norwich City", "Leeds", 2, 1)])
    assert r["resume"]["accords"] == 1 and r["resume"]["ecart_de_date_jours"] == {"1": 1}


def test_appariement_sans_regarder_le_score_puis_comparaison():
    # le pendant est trouvé par les équipes et la date, pas par le score
    r = run([fd("2026-09-20", "Hull", "Leeds", 0, 0)], [med("2026-09-20", "Hull City", "Leeds", 0, 0)])
    assert r["resume"]["matchs_communs_compares"] == 1


# --- doivent être signalés ou exclus ---------------------------------------------------------------------------------
def test_score_different_liste_comme_desaccord():
    r = run([fd("2026-09-20", "Norwich", "Leeds", 3, 2)], [med("2026-09-20", "Norwich City", "Leeds", 1, 0)])
    assert r["resume"]["desaccords"] == 1 and not r["resume"]["critere_atteint"]
    assert r["desaccords"][0]["score_football_data"] == "3-2" and r["desaccords"][0]["score_matchendirect"] == "1-0"


def test_equipe_non_reliee_jamais_comparee():
    r = run([fd("2026-09-20", "Norwich", "Derby", 2, 1)], [med("2026-09-20", "Norwich City", "Derby", 0, 5)])
    assert r["resume"]["matchs_communs_compares"] == 0


def test_deux_jours_d_ecart_pas_apparie():
    r = run([fd("2026-09-20", "Norwich", "Leeds", 2, 1)], [med("2026-09-22", "Norwich City", "Leeds", 0, 0)])
    assert r["resume"]["matchs_communs_compares"] == 0 and r["resume"]["communs_sans_pendant_unique"] == 1


def test_doublon_et_date_future_signales():
    m = fd("2026-09-20", "Norwich", "Leeds", 2, 1)
    r = run([m, dict(m), fd("2026-10-01", "Hull", "Leeds", 0, 0)], [])
    assert r["resume"]["doublons"] == 1 and r["resume"]["dates_futures"] == 1
