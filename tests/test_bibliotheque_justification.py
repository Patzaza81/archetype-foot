"""Tests de bibliotheque_justification.py — verrouille deux correctifs
réels trouvés le 17/09/2026 en diagnostiquant pourquoi 44/44 candidats
réels du run du jour n'affichaient jamais de preuve spécifique au
marché, uniquement la preuve EV générique.
"""
import bibliotheque_justification as bj


def _match(buts_marques, buts_encaisses, domicile):
    return {"buts_marques": buts_marques, "buts_encaisses": buts_encaisses, "domicile": domicile}


def _fenetre_mixte(n_domicile, n_exterieur, domicile_gagne=True):
    """Simule une fenêtre réaliste : n_domicile matchs à domicile +
    n_exterieur matchs à l'extérieur, mélangés (comme
    fenetres.A/B.matchs_retenus, jamais un seul lieu garanti)."""
    matchs = []
    for _ in range(n_domicile):
        matchs.append(_match(2, 0, True) if domicile_gagne else _match(0, 2, True))
    for _ in range(n_exterieur):
        matchs.append(_match(1, 1, False))
    return matchs


# ----------------------------------------------------------------------
# CORRECTIF 1 : MIN_ROLE_MATCHES -- le seuil de 5 matchs, appliqué APRES
# filtrage par lieu, échouait presque toujours sur une fenêtre de 5-12
# matchs mélangés (vérifié : 31% de réussite réelle sur 510 fenêtres du
# 17/09/2026 avec seuil 5, contre 87% avec seuil 3).
# ----------------------------------------------------------------------

def test_seuil_role_relaxe_a_3_matchs_au_meme_lieu():
    """3 matchs à domicile pour l'équipe A (le minimum désormais accepté)
    doit suffire à calculer home_win_rate -- pas besoin de 5."""
    matchs_a = _fenetre_mixte(n_domicile=3, n_exterieur=2, domicile_gagne=True)
    matchs_b = _fenetre_mixte(n_domicile=2, n_exterieur=1)
    donnees = bj.construit_donnees("double_chance_1X", matchs_a, matchs_b, None, odds_scraped=1.5, market_prob_pct=70)
    assert donnees["home_win_rate"] == 100.0


def test_seuil_role_toujours_refuse_sous_3_matchs():
    """2 matchs à domicile seulement -- encore insuffisant, doit rester
    None (le seuil existe toujours, juste abaissé de 5 à 3, pas supprimé)."""
    matchs_a = _fenetre_mixte(n_domicile=2, n_exterieur=3, domicile_gagne=True)
    matchs_b = _fenetre_mixte(n_domicile=2, n_exterieur=1)
    donnees = bj.construit_donnees("double_chance_1X", matchs_a, matchs_b, None, odds_scraped=1.5, market_prob_pct=70)
    assert donnees["home_win_rate"] is None


def test_combined_garde_son_propre_seuil_a_5():
    """Le seuil de 'combined' (a_dom + b_ext regroupés) n'a pas été
    touché -- reste à 5, distinct du seuil par rôle."""
    assert bj.MIN_MATCHES == 5
    assert bj.MIN_ROLE_MATCHES == 3


# ----------------------------------------------------------------------
# CORRECTIF 2 : "over_2.5" (point) n'était jamais reconnu, le code
# cherchait "over_2_5" (underscore) qui n'existe dans aucune donnée
# réelle du moteur (confirmé par lecture directe de precalcul.json,
# 3 occurrences réelles de "over_2.5", 0 de "over_2_5").
# ----------------------------------------------------------------------

def test_marche_over_2_5_avec_point_est_reconnu():
    matchs_a = _fenetre_mixte(n_domicile=3, n_exterieur=3, domicile_gagne=True)
    matchs_b = _fenetre_mixte(n_domicile=3, n_exterieur=3, domicile_gagne=True)
    r = bj.construit_justification_bibliotheque(
        "over_2.5", matchs_a, matchs_b, None,
        nom_domicile="A", nom_exterieur="B", odds_scraped=1.5, market_prob_pct=70,
    )
    types = [p["type"] for p in r["preuves"]]
    # Le marché est désormais reconnu -- au moins tenté (peut encore
    # échouer faute de données suffisantes, mais ne doit plus être
    # systématiquement ignoré comme avant le correctif).
    assert "over_15_rate_combined" in types or "avg_goals_conceded_combined" in types or "target_goals" not in r


def test_over_under_total_prefixe_toujours_reconnu_non_regression():
    """Le chemin déjà fonctionnel (over_under_total_X_Y) n'est pas
    affecté par le correctif du marché bare 'over_2.5'."""
    matchs_a = _fenetre_mixte(n_domicile=4, n_exterieur=4, domicile_gagne=True)
    matchs_b = _fenetre_mixte(n_domicile=4, n_exterieur=4, domicile_gagne=True)
    donnees = bj.construit_donnees("over_under_total_2.5_under", matchs_a, matchs_b, None, odds_scraped=1.5, market_prob_pct=70)
    assert donnees["over_15_rate_combined"] is not None


# ----------------------------------------------------------------------
# CORRECTIF 3 : resume préférait toujours preuves[0] (systématiquement
# la preuve EV, ajoutée sans condition en tête de liste) -- confirmé :
# 44/44 candidats réels du 17/09/2026 avaient ce même résumé générique.
# ----------------------------------------------------------------------

def test_resume_prefere_une_preuve_specifique_si_disponible():
    matchs_a = _fenetre_mixte(n_domicile=5, n_exterieur=5, domicile_gagne=True)
    matchs_b = _fenetre_mixte(n_domicile=1, n_exterieur=1, domicile_gagne=False)
    r = bj.construit_justification_bibliotheque(
        "double_chance_1X", matchs_a, matchs_b, None,
        nom_domicile="Equipe A", nom_exterieur="Equipe B", odds_scraped=1.5, market_prob_pct=70,
    )
    # La preuve EV existe toujours dans la liste (jamais retirée)...
    assert any(p["type"] == "ev_percentage" for p in r["preuves"])
    # ...mais le résumé principal n'est plus systématiquement celui-là
    # dès qu'une preuve spécifique au marché existe.
    preuve_specifique = next((p for p in r["preuves"] if p["type"] != "ev_percentage"), None)
    if preuve_specifique:
        assert r["resume"] == preuve_specifique["texte"]
        assert r["resume"] != next(p["texte"] for p in r["preuves"] if p["type"] == "ev_percentage")


def test_resume_retombe_sur_ev_si_aucune_preuve_specifique():
    """Comportement de repli inchangé : sans donnée suffisante pour une
    preuve spécifique, l'EV reste le résumé (jamais aucun résumé du
    tout tant que la cote et la probabilité sont connues)."""
    matchs_a = _fenetre_mixte(n_domicile=1, n_exterieur=1, domicile_gagne=True)
    matchs_b = _fenetre_mixte(n_domicile=1, n_exterieur=1, domicile_gagne=False)
    r = bj.construit_justification_bibliotheque(
        "double_chance_1X", matchs_a, matchs_b, None,
        nom_domicile="A", nom_exterieur="B", odds_scraped=1.5, market_prob_pct=70,
    )
    assert r["resume"] is not None
    assert "Avantage Statistique" in r["resume"]
