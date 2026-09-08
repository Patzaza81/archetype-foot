"""
archetype_model/poisson/markets.py — Marchés ESSENTIELS uniquement,
dérivés de la matrice de Poisson (v3 §7/§9). PÉRIMÈTRE RÉDUIT
explicitement assumé (contrainte de temps, décision du 08/09/2026) :

    FAIT ici       : 1X2, Double Chance, BTTS, Over/Under total, buts
                      par équipe (Over/Under, §9.4.1/9.4.2)
    PAS FAIT ici   : Handicap au quart de but (§9.3, CORRECTIF 12),
                      marchés combinés DC+Total (§9.4.3/9.4.4),
                      référentiel central formel (§9.1, market_family/
                      exposure_group) -- chantiers séparés, non commencés.

Toutes les fonctions sont PURES : prennent une matrice déjà construite
(poisson.distribution.matrice_scores) ou une distribution marginale
déjà construite (poisson.distribution.distribution_marginale), ne
recalculent jamais un λ ni ne connaissent la source des données.

GESTION DE L'ABSENT : matrice/distribution None (λ manquant en amont)
-> toute fonction ici renvoie None, jamais un crash ni une probabilité
inventée.
"""


def _somme_cellules(matrice, condition):
    """Somme des cellules matrice[x][y] où condition(x, y) est vraie."""
    total = 0.0
    for x, ligne in enumerate(matrice):
        for y, p in enumerate(ligne):
            if condition(x, y):
                total += p
    return total


def probabilites_1x2(matrice):
    """P(victoire domicile), P(nul), P(victoire extérieur)."""
    if matrice is None:
        return None
    p_domicile = _somme_cellules(matrice, lambda x, y: x > y)
    p_nul = _somme_cellules(matrice, lambda x, y: x == y)
    p_exterieur = _somme_cellules(matrice, lambda x, y: x < y)
    return {"domicile": p_domicile, "nul": p_nul, "exterieur": p_exterieur}


def probabilites_double_chance(matrice):
    """P(1X) = P(domicile ou nul), P(X2) = P(nul ou extérieur),
    P(12) = P(domicile ou extérieur) -- dérivées de probabilites_1x2,
    jamais recalculées indépendamment (cohérence garantie par
    construction : 1X + X2 + 12 - (1+X+2) == 1 toujours)."""
    p = probabilites_1x2(matrice)
    if p is None:
        return None
    return {
        "1X": p["domicile"] + p["nul"],
        "X2": p["nul"] + p["exterieur"],
        "12": p["domicile"] + p["exterieur"],
    }


def probabilite_btts(matrice):
    """P(les deux équipes marquent) = 1 - P(X=0) - P(Y=0) + P(X=0,Y=0)
    (inclusion-exclusion, pas une approximation)."""
    if matrice is None:
        return None
    p_x0 = sum(matrice[0])
    p_y0 = sum(ligne[0] for ligne in matrice)
    p_x0_y0 = matrice[0][0]
    return 1.0 - p_x0 - p_y0 + p_x0_y0


def probabilites_over_under_total(matrice, ligne):
    """Over/Under sur le total de buts du match (x+y), lue sur la
    matrice jointe. `ligne` en X.5 par construction du marché --aucune
    cellule ne peut être exactement sur la ligne, over+under == 1.0
    toujours (à la troncature de la matrice près, voir distribution.py)."""
    if matrice is None:
        return None
    over = _somme_cellules(matrice, lambda x, y: (x + y) > ligne)
    under = _somme_cellules(matrice, lambda x, y: (x + y) < ligne)
    return {"over": over, "under": under}


def probabilites_buts_equipe(distribution_marginale_equipe, ligne):
    """Over/Under sur le nombre de buts d'UNE SEULE équipe (v3 §9.4.1/
    9.4.2), lue sur sa distribution marginale -- PAS la matrice jointe,
    c'est la différence explicite avec probabilites_over_under_total.
    `ligne` en X.5 par construction."""
    if distribution_marginale_equipe is None:
        return None
    over = sum(p for k, p in enumerate(distribution_marginale_equipe) if k > ligne)
    under = sum(p for k, p in enumerate(distribution_marginale_equipe) if k < ligne)
    return {"over": over, "under": under}
