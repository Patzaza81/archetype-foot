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


# --- Correctifs du 05/11/2026 : un championnat Matchendirect = une seule division ; nom identique prioritaire ---------------------
MLS = "Etats-Unis : MLS"


def _usa(extra_fd=(), extra_med=()):
    fds = [fd("2026-09-01", "Seattle", "Portland", 1, 0, "USA"), fd("2026-09-08", "Seattle", "Portland", 2, 1, "USA"),
           fd("2026-09-02", "Austin", "Dallas", 3, 1, "USA"), fd("2026-09-09", "Austin", "Dallas", 0, 0, "USA")]
    meds = [med("2026-09-01", "Seattle", "Portland", 1, 0, MLS), med("2026-09-08", "Seattle", "Portland", 2, 1, MLS),
            med("2026-09-02", "Austin", "Dallas", 3, 1, MLS), med("2026-09-09", "Austin", "Dallas", 0, 0, MLS)]
    return fds + list(extra_fd), meds + list(extra_med)


def _sc2_montrose():
    return ([fd("2026-09-03", "Montrose", "Elgin", 2, 0, "SC2"), fd("2026-09-10", "Montrose", "Elgin", 1, 1, "SC2")],
            [med("2026-09-03", "Montreal", "Zzz Qqq", 2, 0, MLS), med("2026-09-10", "Montreal", "Zzz Qqq", 1, 1, MLS)])


# doivent réussir
def test_division_unique_sur_son_championnat_conservee():
    div, amb, _ = ae.construit_correspondances(*_usa())
    assert set(div) == {"USA"} and len(div["USA"]["equipes"]) == 4 and amb == []


def test_deux_divisions_deux_championnats_toutes_deux_conservees():
    fds, meds = _usa([fd("2026-09-05", "Leeds", "Hull", 1, 0, "E1"), fd("2026-09-12", "Leeds", "Hull", 2, 0, "E1")],
                     [med("2026-09-05", "Leeds", "Hull", 1, 0), med("2026-09-12", "Leeds", "Hull", 2, 0)])
    div, amb, _ = ae.construit_correspondances(fds, meds)
    assert set(div) == {"USA", "E1"} and amb == []


def test_division_majoritaire_garde_le_championnat():
    fds, meds = _usa(*_sc2_montrose())
    div, amb, _ = ae.construit_correspondances(fds, meds)
    assert "USA" in div and len(div["USA"]["equipes"]) == 4


# doivent échouer (rejetées)
def test_division_minoritaire_ecartee_montrose_n_est_plus_relie_a_montreal():
    fds, meds = _usa(*_sc2_montrose())
    div, _, _ = ae.construit_correspondances(fds, meds)
    assert "SC2" not in div and all("Montrose" not in d["equipes"] for d in div.values())


def test_division_ecartee_signalee_comme_ambigue():
    fds, meds = _usa(*_sc2_montrose())
    _, amb, _ = ae.construit_correspondances(fds, meds)
    assert {a["division"] for a in amb} == {"SC2"} and ("Montrose", "Montreal") in {(a["football_data"], a["matchendirect"]) for a in amb}


def test_egalite_entre_deux_divisions_aucune_ne_garde_le_championnat():
    fds = [fd("2026-09-03", "Montrose", "Elgin", 2, 0, "SC2"), fd("2026-09-10", "Montrose", "Elgin", 1, 1, "SC2"),
           fd("2026-09-01", "Seattle", "Portland", 1, 0, "USA"), fd("2026-09-08", "Seattle", "Portland", 2, 1, "USA")]
    meds = [med("2026-09-03", "Montreal", "Zzz Qqq", 2, 0, MLS), med("2026-09-10", "Montreal", "Zzz Qqq", 1, 1, MLS),
            med("2026-09-01", "Seattle", "Zzz Www", 1, 0, MLS), med("2026-09-08", "Seattle", "Zzz Www", 2, 1, MLS)]
    div, amb, _ = ae.construit_correspondances(fds, meds)
    assert div == {} and {a["division"] for a in amb} == {"SC2", "USA"}


SC0 = {"SC0": {"competition_matchendirect": "Ecosse : Premier Ligue",
               "equipes": {"Aberdeen": {"matchendirect": "Aberdeen", "preuves": 5, "similarite_nom": 1.0},
                           "Dundee": {"matchendirect": "Dundee FC", "preuves": 5, "similarite_nom": 1.0},
                           "Dundee United": {"matchendirect": "Dundee Utd.", "preuves": 5, "similarite_nom": 1.0}}}}


def _cle(slug, comp="ecosse : premier ligue"):
    return f"https://www.matchendirect.fr/equipe/{slug}_abcdefghijklmnopqrst1.html||{comp}"


# doivent réussir
def test_dundee_fc_relie_a_dundee():
    assert ae._equipe_du_cache(_cle("dundee-fc"), SC0) == ("SC0", "Dundee", "Dundee FC")


def test_dundee_utd_relie_a_dundee_united():
    assert ae._equipe_du_cache(_cle("dundee-utd"), SC0) == ("SC0", "Dundee United", "Dundee Utd.")


def test_club_au_nom_unique_toujours_relie():
    assert ae._equipe_du_cache(_cle("aberdeen"), SC0) == ("SC0", "Aberdeen", "Aberdeen")


# doivent échouer (restent non reliés)
def test_club_inconnu_non_relie():
    assert ae._equipe_du_cache(_cle("hamilton"), SC0) is None


def test_nom_ambigu_sans_nom_identique_non_relie():
    assert ae._equipe_du_cache(_cle("dundee-rovers"), SC0) is None


def test_meme_nom_autre_championnat_non_relie():
    assert ae._equipe_du_cache(_cle("dundee-fc", "angleterre : championnat"), SC0) is None


# --- Correctif du 06/11/2026 : même club écrit de deux façons par Football-Data ----------------------------------------------------
def _deux_graphies(n_long, n_court, long="Sheffield United", court="Sheffield Utd", nom_med="Sheffield Utd"):
    fds, meds = [], []
    for i in range(n_long):
        j = f"2026-09-{i + 1:02d}"
        fds.append(fd(j, long, f"Adv{i}", 1, 0)); meds.append(med(j, nom_med, f"Adv{i}", 1, 0))
    for i in range(n_court):
        j = f"2026-10-{i + 1:02d}"
        fds.append(fd(j, court, f"Autre{i}", 2, 1)); meds.append(med(j, nom_med, f"Autre{i}", 2, 1))
    return fds, meds


# doivent réussir
def test_graphie_majoritaire_gardee_sheffield():
    div, amb, _ = ae.construit_correspondances(*_deux_graphies(13, 1))
    assert div["E1"]["equipes"]["Sheffield United"]["matchendirect"] == "Sheffield Utd" and "Sheffield Utd" not in div["E1"]["equipes"]
    assert [(a["football_data"]) for a in amb] == ["Sheffield Utd"]


def test_graphie_majoritaire_gardee_oxford():
    div, _, _ = ae.construit_correspondances(*_deux_graphies(12, 1, "Oxford", "Oxford Utd", "Oxford Utd"))
    assert "Oxford" in div["E1"]["equipes"] and "Oxford Utd" not in div["E1"]["equipes"]


def test_graphie_unique_toujours_reliee():
    div, amb, _ = ae.construit_correspondances(*_deux_graphies(5, 0))
    assert "Sheffield United" in div["E1"]["equipes"] and amb == []


# doivent échouer (tous rejetés)
def test_egalite_de_preuves_deux_graphies_rejetees():
    div, amb, _ = ae.construit_correspondances(*_deux_graphies(3, 3))
    assert not {"Sheffield United", "Sheffield Utd"} & set(div.get("E1", {}).get("equipes", {})) and {a["football_data"] for a in amb} == {"Sheffield United", "Sheffield Utd"}


def test_pas_de_majorite_nette_rejetees():
    div, amb, _ = ae.construit_correspondances(*_deux_graphies(5, 3))
    assert not {"Sheffield United", "Sheffield Utd"} & set(div.get("E1", {}).get("equipes", {})) and len(amb) == 2


def test_minoritaire_a_une_preuve_et_majoritaire_a_une_preuve_rejetees():
    div, amb, _ = ae.construit_correspondances(*_deux_graphies(1, 1))
    assert not {"Sheffield United", "Sheffield Utd"} & set(div.get("E1", {}).get("equipes", {})) and len(amb) == 2


# --- CORRECTIF 06/11/2026 : une preuve + concurrentes qui ne sont que des adversaires (Bodo/Glimt, Aalesund…) --------------
NOR_C = "Norvège : Eliteserien"
def _bodo(inverse=False):
    fds = [fd("2026-09-12", "Aalesund", "Molde", 2, 0, "NOR"), fd("2026-09-13", "Rosenborg", "Viking", 3, 1, "NOR")]
    meds = [med("2026-09-12", "Aalesund", "Qwerty", 2, 0, NOR_C), med("2026-09-12", "Altrincham", "Molde", 2, 0, "Angleterre : Ligue Nationale"), med("2026-09-13", "Rosenborg", "Viking", 3, 1, NOR_C)]
    return fds, (meds[::-1] if inverse else meds)

def test_une_preuve_concurrente_simple_adversaire_relie_nom_identique():
    div, _, _ = ae.construit_correspondances(*_bodo())
    assert div["NOR"]["equipes"]["Aalesund"]["matchendirect"] == "Aalesund"

def test_une_preuve_resultat_independant_de_l_ordre_des_matchs():
    assert ae.construit_correspondances(*_bodo())[0] == ae.construit_correspondances(*_bodo(inverse=True))[0]

def test_une_preuve_bon_choix_meme_si_la_concurrente_vient_en_premier():
    fds, meds = _bodo(); div, _, _ = ae.construit_correspondances(fds, [meds[1], meds[0], meds[2]])
    assert div["NOR"]["equipes"]["Aalesund"]["matchendirect"] == "Aalesund" and "Altrincham" not in str(div["NOR"]["equipes"]["Aalesund"])

def test_une_preuve_concurrente_au_nom_assez_semblable_reste_non_resolue():
    fds = [fd("2026-09-12", "Molde", "Brann", 1, 0, "NOR")]
    meds = [med("2026-09-12", "Molde", "Zzz", 1, 0, NOR_C), med("2026-09-12", "Fylde", "Brann", 1, 0, "Angleterre : Ligue Nationale")]
    div, _, nr = ae.construit_correspondances(fds, meds)
    assert "Molde" not in div.get("NOR", {}).get("equipes", {}) and any(x["football_data"] == "Molde" for x in nr)

def test_une_preuve_noms_presque_identiques_hors_championnat_dominant_non_relie():
    fds = [fd("2026-09-12", "Annan Athletic", "Edinburgh City", 0, 0, "SC3"), fd("2026-09-19", "Dumbarton", "Edinburgh City", 2, 1, "SC3")]
    meds = [med("2026-09-12", "Athletic Club", "Rival", 0, 0, "Espagne : LaLiga"), med("2026-09-12", "Dundee FC", "Edinburgh City", 0, 0, "Écosse : Ligue 2"),
            med("2026-09-19", "Dumbarton", "Edinburgh City", 2, 1, "Écosse : Ligue 2")]
    div, _, nr = ae.construit_correspondances(fds, meds)
    assert "Annan Athletic" not in div.get("SC3", {}).get("equipes", {}) and any(x["football_data"] == "Annan Athletic" for x in nr)

def test_une_preuve_candidate_peu_semblable_jamais_acceptee():
    div, _, nr = ae.construit_correspondances([fd("2026-09-12", "Brann", "Molde", 1, 0, "NOR")], [med("2026-09-12", "Zzz", "Molde", 1, 0, NOR_C), med("2026-09-12", "Yyy", "Wxx", 1, 0, NOR_C)])
    assert "Brann" not in div.get("NOR", {}).get("equipes", {})

def test_une_preuve_championnats_a_egalite_dominant_inconnu_non_relie():
    fds = [fd("2026-09-12", "Aalesund", "Molde", 2, 0, "NOR")]
    meds = [med("2026-09-12", "Aalesund", "Qwerty", 2, 0, NOR_C), med("2026-09-12", "Altrincham", "Molde", 2, 0, "Angleterre : Ligue Nationale")]
    for ordre in (meds, meds[::-1]):
        div, _, nr = ae.construit_correspondances(fds, ordre)
        assert "Aalesund" not in div.get("NOR", {}).get("equipes", {}) and any(x["football_data"] == "Aalesund" for x in nr)
