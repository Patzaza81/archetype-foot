"""Handicap à 3 choix BetPawa (28/09/2026, décision de Patrick) : lecture par les parseurs, isolation V2, calcul V3.

3 cas qui passent / 3 cas qui échouent par règle."""
import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import moteur_v3_pipeline as mp  # noqa: E402
import pont_moteur  # noqa: E402
from moteur_v3.markets import gagne  # noqa: E402
from parse_betpawa_playwright import parse_betpawa_playwright  # noqa: E402
from parse_betpawa_url import parse_betpawa_url  # noqa: E402

# Texte réel de la page (format navigateur automatisé : étiquette et cote sur deux lignes).
BLOC_PW = """3-Way Handicap | Full Time
1
X
2
Home -2
17.05
Home -2
8.56
Away +2
1.07
Home -1
6.42
Home -1
4.73
Away +1
1.35
Home +1
1.55
Away -1
4.14
Away -1
4.49
Home +2
1.15
Away -2
6.76
Away -2
10.95
Home +3
1.01
Away -3
12.61
Away -3
12.73
Odd/Even | Full Time
Odd
1.90
Even
1.85"""

BLOC_URL = """3-Way Handicap | Full Time
- 1
- X
- 2
Home -217.05
Home -28.56
Away +21.07
Home +11.55
Away -14.14
Away -14.49
Odd/Even | Full Time
Odd1.90
Even1.85"""


# --- Parseurs : 3 passent -------------------------------------------------------------------------------------------
def test_pw_lit_toutes_les_lignes():
    c = parse_betpawa_playwright(BLOC_PW, "A", "B")
    assert c["handicap_3issues_-2"] == {"1": 17.05, "X": 8.56, "2": 1.07}
    assert c["handicap_3issues_-1"] == {"1": 6.42, "X": 4.73, "2": 1.35}
    assert c["handicap_3issues_1"] == {"1": 1.55, "X": 4.14, "2": 4.49}
    assert c["handicap_3issues_2"] == {"1": 1.15, "X": 6.76, "2": 10.95}
    assert c["handicap_3issues_3"] == {"1": 1.01, "X": 12.61, "2": 12.73}


def test_pw_section_suivante_intacte_et_virgule():
    c = parse_betpawa_playwright(BLOC_PW.replace("17.05", "17,05"), "A", "B")
    assert c["handicap_3issues_-2"]["1"] == 17.05
    assert c["pair_impair"] == {"pair": 1.85, "impair": 1.90}


def test_url_format_colle():
    c = parse_betpawa_url(BLOC_URL, "A", "B")
    assert c["handicap_3issues_-2"] == {"1": 17.05, "X": 8.56, "2": 1.07}
    assert c["handicap_3issues_1"] == {"1": 1.55, "X": 4.14, "2": 4.49}
    assert c["pair_impair"] == {"pair": 1.85, "impair": 1.90}


# --- Parseurs : 3 échouent proprement -------------------------------------------------------------------------------
def test_pw_ligne_tronquee_non_enregistree():
    texte = "3-Way Handicap | Full Time\n1\nX\n2\nHome -2\n17.05\nHome -2\n8.56\nAway +2"
    assert parse_betpawa_playwright(texte, "A", "B") == {}


def test_pw_cote_illisible_non_enregistree():
    texte = BLOC_PW.replace("8.56", "SUSPENDU")
    c = parse_betpawa_playwright(texte, "A", "B")
    assert not any(k.startswith("handicap_3issues_") for k in c)


def test_pw_ligne_commencant_par_away_refusee():
    texte = "3-Way Handicap | Full Time\nAway +2\n1.07\nHome -2\n8.56\nHome -2\n17.05"
    assert parse_betpawa_playwright(texte, "A", "B") == {}


# --- Isolation V2 : la clé nouvelle ne change rien au moteur V2 -----------------------------------------------------
BASE_V2 = {"1x2": {"1": 1.9, "N": 3.4, "2": 4.0}, "handicap_-1.5": {"domicile": 3.6, "exterieur": 1.3},
           "handicap_3choix_1": {"domicile": 2.9, "nul": 3.5, "exterieur": 1.4}}


def test_v2_cotes_moteur_identiques():
    avec = copy.deepcopy(BASE_V2)
    avec.update(parse_betpawa_playwright(BLOC_PW, "A", "B"))
    assert pont_moteur.cotes_vers_moteur(avec)[0] == pont_moteur.cotes_vers_moteur(BASE_V2)[0]


def test_v2_cle_differente_de_handicap_3choix():
    c = parse_betpawa_playwright(BLOC_PW, "A", "B")
    assert not any(k.startswith("handicap_3choix") for k in c)
    assert not any(pont_moteur._RE_HANDICAP_3.match(k) or pont_moteur._RE_HANDICAP_2.match(k) for k in c)


# --- V3 : lecture des cotes ------------------------------------------------------------------------------------------
def _enreg(cotes):
    return {"cotes_betpawa": cotes, "cotes_observees": {}}


def test_v3_conversion_ligne_domicile_vers_ligne_v3():
    c = mp.cotes_etendues(_enreg(parse_betpawa_playwright(BLOC_PW, "A", "B")))
    assert c["handicap_2_1"] == 17.05 and c["handicap_2_X"] == 8.56 and c["handicap_2_2"] == 1.07   # Domicile -2
    assert c["handicap_1_1"] == 6.42 and c["handicap_-1_2"] == 4.49 and c["handicap_-2_1"] == 1.15  # -1, +1, +2


def test_v3_deux_choix_toujours_lus():
    c = mp.cotes_etendues(_enreg({"handicap_-1.5": {"domicile": 6.42, "exterieur": 1.08}}))
    assert c == {"handicap_1.5_1": 6.42, "handicap_1.5_2": 1.08}


def test_v3_lignes_entieres_transmises_au_moteur():
    e = _enreg(parse_betpawa_playwright(BLOC_PW, "A", "B"))
    e.update({"equipe_dom": {"matchs": []}, "equipe_ext": {"matchs": []}})
    assert {-2.0, -1.0, 1.0, 2.0} <= set(mp.entree_v3(e)["handicap_lines"])


def test_v3_ligne_3_ignoree_par_choix():
    e = _enreg(parse_betpawa_playwright(BLOC_PW, "A", "B"))
    c = mp.cotes_etendues(e)
    assert not any(k.startswith(("handicap_-3_", "handicap_3_")) for k in c)
    cv = mp.couverture(e, c)
    assert cv["groupes_ignores_par_choix"] == ["handicap_3issues_3"] and cv["groupes_non_lus"] == []


def test_v3_cote_invalide_ignoree():
    c = mp.cotes_etendues(_enreg({"handicap_3issues_1": {"1": 1.0, "X": None, "2": "abc"}}))
    assert c == {}


def test_v3_cle_3choix_copier_coller_non_lue():
    c = mp.cotes_etendues(_enreg({"handicap_3choix_1": {"domicile": 2.9, "nul": 3.5, "exterieur": 1.4}}))
    assert c == {}


# --- Sens des paris : libellé, résultat réel et règle doivent dire la même chose ----------------------------------
# Condition gagnante, écrite à la main, de chaque pari couvert par une règle du double contrôle.
REGLES = {"Handicap domicile -1.5": lambda h, a: h - a >= 2, "Handicap domicile +1.5": lambda h, a: a - h <= 1,
          "Handicap extérieur -1.5": lambda h, a: a - h >= 2, "Handicap extérieur +1.5": lambda h, a: h - a <= 1,
          "Double chance - 1X": lambda h, a: h >= a, "Double chance - X2": lambda h, a: a >= h,
          "1X2 - 1": lambda h, a: h > a, "1X2 - 2": lambda h, a: a > h}
SCORES = [(h, a) for h in range(8) for a in range(8)]
TROIS_CHOIX = [f"handicap_{l}_{o}" for l in (-2, -1, 1, 2) for o in ("1", "X", "2")]


@pytest.mark.parametrize("marche", [m for m in mp.DOUBLE_CONTROLE if m.startswith("handicap_")])
def test_regle_identique_au_pari(marche):
    regle = REGLES[mp.DOUBLE_CONTROLE[marche]]
    assert all(gagne(marche, h, a) == regle(h, a) for h, a in SCORES)


@pytest.mark.parametrize("marche,score_gagnant,score_perdant", [
    ("handicap_1_1", (3, 1), (2, 1)), ("handicap_1_X", (2, 1), (1, 1)), ("handicap_1_2", (1, 1), (2, 1)),
    ("handicap_-2_1", (0, 1), (0, 2)), ("handicap_-2_X", (0, 2), (0, 1)), ("handicap_2_2", (2, 1), (3, 1))])
def test_trois_choix_resultat_reel(marche, score_gagnant, score_perdant):
    assert gagne(marche, *score_gagnant) is True and gagne(marche, *score_perdant) is False


def test_trois_issues_exclusives_et_completes():
    for l in (-2, -1, 1, 2):
        for h, a in SCORES:
            assert sum(gagne(f"handicap_{l}_{o}", h, a) for o in ("1", "X", "2")) == 1


@pytest.mark.parametrize("marche,attendu", [
    ("handicap_1_1", "Handicap 3 choix Domicile −1 (1) : Domicile gagne par 2 buts ou plus"),
    ("handicap_-1_X", "Handicap 3 choix Domicile +1 (X) : Extérieur gagne par exactement 1 but"),
    ("handicap_-0.5_1", "Handicap Domicile +0,5 : Domicile ne perd pas")])
def test_libelles_handicap(marche, attendu):
    assert mp.libelle(marche) == attendu


def test_libelle_avec_noms_equipes():
    assert (mp.libelle_handicap("handicap_2_2", "Rudar", "Dravinja")
            == "Handicap 3 choix Rudar −2 (2) : Dravinja ne perd pas par 2 buts ou plus")


def test_issues_sans_regle_jamais_selectionnables():
    sans = {"handicap_1_X", "handicap_-1_X", "handicap_2_X", "handicap_-2_X", "handicap_2_1", "handicap_-2_2"}
    assert sans == {m for m in TROIS_CHOIX if m not in mp.DOUBLE_CONTROLE}


def test_nom_site_distinct_deux_et_trois_choix():
    assert mp.nom_site("handicap_1_1") == "handicap3_domicile_-1_1"
    assert mp.nom_site("handicap_1.5_1") == "handicap_domicile_-1.5"
    assert len({mp.nom_site(m) for m in TROIS_CHOIX}) == 12


def test_phrase_calcul_issue_nulle():
    assert mp.phrase_calcul("handicap_1_X") == "Somme des scores où buts domicile − 1 = buts extérieur."
