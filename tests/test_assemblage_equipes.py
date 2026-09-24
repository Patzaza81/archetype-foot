"""A3 (correspondance des noms) et A4 bis (assemblage Football-Data / Matchendirect) — 24/09/2026.
Cas qui doivent réussir et cas qui doivent échouer, dont les règles de Patrick : jours manquants complétés par
Matchendirect, dates vérifiées à ± 1 jour, match provisoire remplacé par Football-Data dès sa publication."""
import datetime

import assemblage_equipes as ae

D = datetime.date


def fd(date, dom, ext, h, a, div="E1", **extra):
    m = {"date": date, "home_team": dom, "away_team": ext, "full_time_home_goals": h, "full_time_away_goals": a,
         "competition_code": div, "season": "2627", "half_time_home_goals": 0, "half_time_away_goals": 0,
         "home_corners": 5, "away_corners": 3}
    m.update(extra)
    return m


def med(date, dom, ext, h, a, comp="Angleterre : Championnat"):
    return {"date": D.fromisoformat(date), "domicile": dom, "exterieur": ext, "competition": comp, "buts": (h, a)}


# --- A3 : doivent être reliées ---------------------------------------------------------------------------------------
def test_deux_preuves_nom_different_relie_grace_a_l_adversaire():
    fds = [fd("2026-09-12", "Mainz", "Bochum", 2, 1, "D1"), fd("2026-09-20", "Freiburg", "Mainz", 0, 0, "D1")]
    meds = [med("2026-09-12", "Mayence", "Bochum", 2, 1, "Allemagne : Bundesliga"),
            med("2026-09-20", "Fribourg", "Mayence", 0, 0, "Allemagne : Bundesliga")]
    div, amb, nr = ae.construit_correspondances(fds, meds)
    assert div["D1"]["equipes"]["Mainz"]["matchendirect"] == "Mayence"
    assert div["D1"]["competition_matchendirect"] == "Allemagne : Bundesliga"


def test_une_preuve_noms_presque_identiques_relie():
    div, _, _ = ae.construit_correspondances([fd("2026-09-12", "Burton", "Wigan", 1, 0, "E2")],
                                             [med("2026-09-12", "Burton Albion", "Wigan", 1, 0, "Angleterre : League One")])
    assert div["E2"]["equipes"]["Burton"]["matchendirect"] == "Burton Albion"


def test_date_decalee_d_un_jour_acceptee_mls():
    div, _, _ = ae.construit_correspondances([fd("2026-09-20", "Austin FC", "San Diego", 2, 1, "USA")],
                                             [med("2026-09-21", "Austin", "San Diego", 2, 1, "Etats-Unis : MLS")])
    assert div["USA"]["equipes"]["Austin FC"]["matchendirect"] == "Austin"


# --- A3 : doivent être refusées --------------------------------------------------------------------------------------
def test_une_seule_preuve_nom_different_non_resolu():
    div, _, nr = ae.construit_correspondances([fd("2026-09-12", "Den Haag", "Volendam", 1, 0, "N1")],
                                              [med("2026-09-12", "ADO", "Volendam", 1, 0, "Pays-Bas : Eredivisie")])
    assert "Den Haag" not in div.get("N1", {}).get("equipes", {})
    assert any(x["football_data"] == "Den Haag" for x in nr)


def test_meme_score_meme_date_noms_tous_differents_aucune_preuve():
    div, _, nr = ae.construit_correspondances([fd("2026-09-12", "Leeds", "Hull", 1, 0)],
                                              [med("2026-09-12", "Marseille", "Lyon", 1, 0, "France : Ligue 1")])
    assert div == {} and nr == []


def test_deux_jours_d_ecart_aucune_preuve():
    div, _, _ = ae.construit_correspondances([fd("2026-09-12", "Leeds", "Hull", 1, 0)],
                                             [med("2026-09-14", "Leeds", "Hull", 1, 0)])
    assert div == {}


def test_nom_revendique_par_deux_equipes_rejete():
    # deux équipes Football-Data ayant chacune 2 preuves vers le même nom Matchendirect : aucune n'est retenue
    fds = [fd("2026-09-12", "Man City", "Hull", 1, 0), fd("2026-09-15", "Man City", "Derby", 3, 0),
           fd("2026-09-13", "Man United", "Leeds", 2, 0), fd("2026-09-16", "Man United", "Wigan", 4, 0)]
    meds = [med("2026-09-12", "Manchester", "Hull", 1, 0), med("2026-09-15", "Manchester", "Derby", 3, 0),
            med("2026-09-13", "Manchester", "Leeds", 2, 0), med("2026-09-16", "Manchester", "Wigan", 4, 0)]
    div, amb, _ = ae.construit_correspondances(fds, meds)
    assert {a["football_data"] for a in amb} == {"Man City", "Man United"}
    assert "Man City" not in div.get("E1", {}).get("equipes", {})


# --- A4 bis : assemblage ---------------------------------------------------------------------------------------------
DIVISIONS = {"E1": {"competition_matchendirect": "Angleterre : Championnat",
                    "equipes": {"Norwich": {"matchendirect": "Norwich", "preuves": 5, "similarite_nom": 1.0}}}}
CLE = "https://www.matchendirect.fr/equipe/norwich_abc.html||angleterre : championnat"


def cache(*matchs):
    return {CLE: {"resultat": {"matchs_domicile_bruts": [m for m in matchs if m["domicile"]],
                               "matchs_exterieur_bruts": [m for m in matchs if not m["domicile"]]}}}


def m_med(date, dom, adv, bm, be):
    return {"date": date, "domicile": dom, "adversaire": adv, "buts_marques": bm, "buts_encaisses": be, "url_match": "/x"}


def test_football_data_en_base_et_jour_manquant_complete_provisoire():
    fds = [fd("2026-09-20", "Norwich", "Hull", 2, 1)]
    eq, b = ae.assemble(cache(m_med("2026-09-20", True, "Hull", 2, 1), m_med("2026-09-23", False, "Leeds", 0, 0)), fds, DIVISIONS)
    matchs = eq[0]["matchs"]
    assert [(x["date"], x["source"], x["provisoire"]) for x in matchs] == [
        ("2026-09-20", "football-data", False), ("2026-09-23", "matchendirect", True)]
    assert matchs[0]["corners"] == 5 and matchs[0]["buts_marques_mi_temps"] == 0      # données complètes Football-Data
    assert b["doublons_evites"] == 1


def test_meme_match_date_decalee_d_un_jour_jamais_compte_deux_fois():
    fds = [fd("2026-09-20", "Norwich", "Hull", 2, 1)]
    eq, _ = ae.assemble(cache(m_med("2026-09-21", True, "Hull", 2, 1)), fds, DIVISIONS)
    assert len(eq[0]["matchs"]) == 1 and eq[0]["matchs"][0]["source"] == "football-data"


def test_provisoire_remplace_par_football_data_des_sa_publication():
    c = cache(m_med("2026-09-23", False, "Leeds", 0, 0))
    run1, _ = ae.assemble(c, [fd("2026-09-20", "Norwich", "Hull", 2, 1)], DIVISIONS)
    assert run1[0]["matchs"][-1]["provisoire"] is True
    run2, _ = ae.assemble(c, [fd("2026-09-20", "Norwich", "Hull", 2, 1), fd("2026-09-23", "Leeds", "Norwich", 0, 0)], DIVISIONS)
    derniers = [x for x in run2[0]["matchs"] if x["date"] == "2026-09-23"]
    assert len(derniers) == 1 and derniers[0]["source"] == "football-data" and derniers[0]["provisoire"] is False


def test_match_matchendirect_sans_date_jamais_ajoute_a_une_equipe_couverte():
    eq, b = ae.assemble(cache(m_med(None, False, "Leeds", 0, 0)), [fd("2026-09-20", "Norwich", "Hull", 2, 1)], DIVISIONS)
    assert len(eq[0]["matchs"]) == 1 and b["matchs_sans_date_ignores"] == 1


def test_championnat_non_couvert_matchendirect_seul_non_provisoire():
    c = {"https://www.matchendirect.fr/equipe/the-new-saints_x.html||pays de galles : cymru premier":
         {"resultat": {"matchs_domicile_bruts": [m_med("2026-09-19", True, "Llandudno", 2, 1)], "matchs_exterieur_bruts": []}}}
    eq, _ = ae.assemble(c, [], DIVISIONS)
    assert eq[0]["couverte_par_football_data"] is False and eq[0]["matchs"][0]["provisoire"] is False
    assert eq[0]["raison"] == "championnat non couvert par Football-Data"
