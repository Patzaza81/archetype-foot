"""Contrôle des données de saison (24/09/2026) : cas qui doivent être jugés cohérents et cas qui doivent être
détectés comme incohérents, dont le cas réel The New Saints (match amical enregistré à la place du championnat)."""
import controle_saisons as cs

URL = "https://www.matchendirect.fr/equipe/the-new-saints_85l2ewv17mqmw3otdletjc36.html"
CLE = URL + "||pays de galles : cymru premier"


def _connu(dom, marques, encaisses, date="2026-09-11", comp="cymru premier", adv="X"):
    return {"domicile": dom, "marques": marques, "encaisses": encaisses, "date": date, "adversaire": adv, "competition": comp}


def _entree(dom=(), ext=(), horodatage="2026-09-24T02:56:55+00:00"):
    return {"horodatage": horodatage, "resultat": {
        "matchs_domicile_bruts": [{"domicile": True, "buts_marques": m, "buts_encaisses": e} for m, e in dom],
        "matchs_exterieur_bruts": [{"domicile": False, "buts_marques": m, "buts_encaisses": e} for m, e in ext]}}


# --- doivent être COHÉRENTS ---------------------------------------------------------------------------------------
def test_saison_complete_coherente():
    connus = {"the new saints": [_connu(False, 2, 0), _connu(True, 5, 0, "2026-09-15")]}
    assert cs.controle_equipe(CLE, _entree(dom=[(5, 0), (2, 1)], ext=[(2, 0)]), connus)["statut"] == "COHERENTE"


def test_match_joue_apres_l_enregistrement_ignore():
    connus = {"the new saints": [_connu(False, 2, 0, "2026-09-25")]}   # joué après l'enregistrement du 24/09
    assert cs.controle_equipe(CLE, _entree(dom=[(1, 0)]), connus)["statut"] == "NON_VERIFIABLE"


def test_match_d_une_autre_competition_ignore():
    connus = {"the new saints": [_connu(True, 3, 0, comp="coupe du pays de galles")]}
    assert cs.controle_equipe(CLE, _entree(dom=[(1, 0)]), connus)["statut"] == "NON_VERIFIABLE"


# --- doivent être INCOHÉRENTS --------------------------------------------------------------------------------------
def test_cas_reel_the_new_saints_match_amical_a_la_place_du_championnat():
    # enregistré : 1-1 à l'extérieur (Glentoran, amical) ; connu : Broughton 0-2 The New Saints (11/09)
    connus = {"the new saints": [_connu(False, 2, 0, adv="Broughton")]}
    ligne = cs.controle_equipe(CLE, _entree(ext=[(1, 1)]), connus)
    assert ligne["statut"] == "INCOHERENTE"
    assert ligne["manquants"] == [{"date": "2026-09-11", "adversaire": "Broughton", "lieu": "extérieur", "score_equipe": "2-0"}]


def test_bon_score_mauvais_lieu_incoherent():
    connus = {"the new saints": [_connu(False, 2, 0)]}
    assert cs.controle_equipe(CLE, _entree(dom=[(2, 0)]), connus)["statut"] == "INCOHERENTE"


def test_un_seul_exemplaire_pour_deux_matchs_identiques_incoherent():
    connus = {"the new saints": [_connu(True, 1, 0, "2026-09-05"), _connu(True, 1, 0, "2026-09-14")]}
    assert cs.controle_equipe(CLE, _entree(dom=[(1, 0)]), connus)["statut"] == "INCOHERENTE"


def test_normalisations():
    assert cs.slug_equipe(URL) == "the new saints"
    assert cs.partie_competition("Pays de Galles :\n  Cymru Premier") == "cymru premier"
    assert cs.normalise("Pérouse") == "perouse"
