import pytest

import journal_indice as ji


def _m(*s):
    return [{"date": f"2026-09-{i + 1:02d}", "domicile": True, "buts_marques": a, "buts_encaisses": b} for i, (a, b) in enumerate(s)]


def _ext(*s):
    return [{"date": f"2026-09-{i + 1:02d}", "domicile": False, "buts_marques": a, "buts_encaisses": b} for i, (a, b) in enumerate(s)]


ENREG = {"date": "2026-10-10", "domicile": "Boston Utd", "exterieur": "Southend Utd",
         "equipe_dom": {"matchs": _m((0, 1), (1, 0), (2, 3), (1, 3), (1, 1), (0, 1))},
         "equipe_ext": {"matchs": _ext((3, 1), (3, 1), (1, 1), (2, 2), (6, 1), (1, 1))}}


@pytest.mark.parametrize("libelle,dom,attendu", [
    ("Ne perd pas (victoire ou nul)", True, "dc_1X"), ("Ne perd pas (victoire ou nul)", False, "dc_X2"),
    ("Marque 2 buts ou plus", False, "away_over_1_5"), ("Victoire", False, "1x2_2"),
    ("Gagne par 2 buts ou plus", True, "handicap_1.5_1"), ("Gagne par 2 buts ou plus", False, "handicap_-1.5_2"),
    ("Garde sa cage inviolée", True, "clean_home")])
def test_marche_moteur_selon_le_cote(libelle, dom, attendu):
    assert ji.marche_moteur(libelle, dom) == attendu


@pytest.mark.parametrize("libelle", ["Marché inconnu", "", "Match à plus de 9,5 buts"])
def test_marche_moteur_inconnu(libelle):
    assert ji.marche_moteur(libelle, True) is None


def test_trouve_match_oui():
    assert ji.trouve_match([ENREG], "Southend Utd", "Boston Utd", "2026-10-10", False) is ENREG
    assert ji.trouve_match([ENREG], "Boston Utd", "Southend Utd", "2026-10-10", True) is ENREG
    assert ji.trouve_match([ENREG], "Southend", "Boston", "2026-10-10", False) is ENREG


@pytest.mark.parametrize("equipe,adv,date,dom", [("Southend Utd", "Boston Utd", "2026-10-11", False),
                                                  ("Southend Utd", "Boston Utd", "2026-10-10", True),      # mauvais côté
                                                  ("Southend Utd", "Lyon", "2026-10-10", False),
                                                  ("Crewe", "Boston Utd", "2026-10-10", False)])
def test_trouve_match_non(equipe, adv, date, dom):
    assert ji.trouve_match([ENREG], equipe, adv, date, dom) is None


def _ligne(marche, lieu="extérieur", equipe="Southend Utd", adv="Boston Utd"):
    return {"equipe": equipe, "marche": marche, "prochain_match": {"date": "2026-10-10", "adversaire": adv, "lieu": lieu}}


def test_indice_southend_x2_3_sur_4():
    p = ji.indice_pour_ligne(_ligne("Ne perd pas (victoire ou nul)"), [ENREG])
    assert (p["indice"], p["sur"], p["libelle"], p["marche_moteur"]) == (3, 4, "Recommandé", "dc_X2")


def test_indice_marche_une_equipe_sur_2():
    p = ji.indice_pour_ligne(_ligne("Marque 2 buts ou plus"), [ENREG])
    assert (p["indice"], p["sur"]) == (1, 2) and "pire match" in p["phrase"]


def test_indice_absent_si_pas_de_match_ou_pas_de_prochain():
    assert ji.indice_pour_ligne(_ligne("Victoire", adv="Lyon"), [ENREG]) is None
    assert ji.indice_pour_ligne({"equipe": "Southend Utd", "marche": "Victoire"}, [ENREG]) is None
    assert ji.indice_pour_ligne(_ligne("Marché inconnu"), [ENREG]) is None


def test_ajoute_indices_ne_touche_pas_au_reste():
    j = {"equipes_a_suivre": [dict(_ligne("Ne perd pas (victoire ou nul)"), gagnes=7, joues=7, frequence=1.0)], "opportunites_futures": []}
    n = ji.ajoute_indices(j, [ENREG])
    assert n == 1 and j["equipes_a_suivre"][0]["frequence"] == 1.0 and j["equipes_a_suivre"][0]["gagnes"] == 7
    assert ji.ajoute_indices({"equipes_a_suivre": [_ligne("Victoire", adv="Lyon")]}, [ENREG]) == 0
