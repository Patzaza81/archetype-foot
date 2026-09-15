"""Audit fonctionnel des marchés réellement retenus par Archetype Foot.

Ce test ne scrape rien : il vérifie le chemin interne réel
libellé Betpawa -> clé interne -> calcul Poisson -> probabilité -> filtre.
"""

from math import isfinite

from archetype_model.data.odds_provider import _parse_libelle
from archetype_model.poisson import markets, distribution
from archetype_model import main


SCENARIOS = ("offensif", "defensif", "contextuel", "global")


def _matrices():
    return {
        s: distribution.matrice_scores(1.45, 1.05)
        for s in SCENARIOS
    }


def test_tous_les_marches_produisent_des_probabilites_valides():
    resultats = markets.calcule_tous_les_marches(1.45, 1.05)
    attendus = {
        "1x2",
        "double_chance",
        "btts",
        "over_under_total",
        "handicap",
        "buts_equipe_domicile",
        "buts_equipe_exterieur",
        "parite_totale",
        "combo_dc_total",
    }
    assert attendus <= set(resultats)

    assert abs(sum(resultats["1x2"].values()) - 1.0) < 1e-9
    assert abs(sum(resultats["double_chance"].values()) - 1.0) < 1e-9
    assert abs(resultats["btts"] + (1.0 - resultats["btts"]) - 1.0) < 1e-9
    assert abs(sum(resultats["parite_totale"].values()) - 1.0) < 1e-9


def test_handicap_3_choix_normalise_les_trois_issues_sur_la_meme_ligne():
    domicile = _parse_libelle("Domicile -3")
    nul = _parse_libelle("Nul -3")
    exterieur = _parse_libelle("Extérieur +3")

    assert domicile == ("handicap_3choix", 3.0, "domicile")
    assert nul == ("handicap_3choix", 3.0, "nul")
    assert exterieur == ("handicap_3choix", 3.0, "exterieur")

    matrices = _matrices()
    dist_a = {s: distribution.distribution_marginale(1.45) for s in SCENARIOS}
    dist_b = {s: distribution.distribution_marginale(1.05) for s in SCENARIOS}

    probs = {}
    for cle, nom in ((domicile, "domicile"), (nul, "nul"), (exterieur, "exterieur")):
        extracteur = main._extracteur_dynamique(cle, matrices, dist_a, dist_b)
        probs[nom] = extracteur("offensif")

    assert all(0.0 <= p <= 1.0 for p in probs.values())
    assert abs(sum(probs.values()) - 1.0) < 1e-9


def test_tous_les_libelles_retenus_sont_parsees_sans_approximation():
    libelles = [
        "1X2 - 1", "1X2 - X", "1X2 - 2",
        "Double chance - 1X", "Double chance - X2", "Double chance - 12",
        "BTTS - oui", "BTTS - non",
        "Plus de 2.5 buts", "Moins de 2.5 buts",
        "Plus de 0.5 buts - Domicile", "Moins de 1.5 buts - Domicile",
        "Plus de 0.5 buts - Extérieur", "Moins de 1.5 buts - Extérieur",
        "Cage inviolée - Domicile", "Encaisse au moins 1 but - Domicile",
        "Cage inviolée - Extérieur", "Encaisse au moins 1 but - Extérieur",
        "Total buts - pair", "Total buts - impair",
        "Domicile -3", "Nul -3", "Extérieur +3",
        "1X + Plus de 1.5 buts", "1X + Moins de 2.5 buts",
        "X2 + Plus de 1.5 buts", "X2 + Moins de 2.5 buts",
        "12 + Plus de 1.5 buts", "12 + Moins de 2.5 buts",
    ]
    assert all(_parse_libelle(libelle) is not None for libelle in libelles)


def test_marches_dynamiques_restent_exploitables_par_le_filtre():
    matrices = _matrices()
    dist_a = {s: distribution.distribution_marginale(1.45) for s in SCENARIOS}
    dist_b = {s: distribution.distribution_marginale(1.05) for s in SCENARIOS}
    cles = [
        ("1x2", "domicile"),
        ("double_chance", "1X"),
        ("btts", "oui"),
        ("over_under_total", 2.5, "over"),
        ("buts_equipe_domicile", 0.5, "over"),
        ("buts_equipe_exterieur", 0.5, "over"),
        ("parite_totale", "pair"),
        ("handicap_3choix", 3.0, "domicile"),
        ("combo_dc_total", "1X", "over", 1.5),
    ]
    for cle in cles:
        extracteur = main._extracteur_dynamique(cle, matrices, dist_a, dist_b)
        assert extracteur is not None
        valeurs = [extracteur(s) for s in SCENARIOS]
        assert all(v is not None and isfinite(v) and 0.0 <= v <= 1.0 for v in valeurs)


def test_handicap_non_retenu_reste_refuse():
    assert _parse_libelle("Handicap asiatique -3") is None
    assert _parse_libelle("Handicap européen +3") is None
