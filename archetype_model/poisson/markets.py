"""
archetype_model/poisson/markets.py — Marchés dérivés de la matrice de
Poisson (v3 §7/§9).

    FAIT ici       : 1X2, Double Chance, BTTS, Over/Under total, buts
                      par équipe (§9.4.1/9.4.2), Handicap au quart de
                      but (§9.3, CORRECTIF 6/12), marchés combinés
                      DC+Total (§9.4.3/9.4.4, COMBO_DC_TOTAL)
    PAS FAIT ici   : référentiel central formel (§9.1, market_family/
                      exposure_group/déduplication) -- chantier séparé,
                      non commencé.

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


def _resultat_handicap_ligne_entiere_ou_demie(matrice, h):
    """Handicap pour une ligne déjà entière ou demi-entière (v3 §9.3,
    CORRECTIF 6) -- dérivée mécaniquement de la matrice, aucun
    paramètre nouveau. Push seulement possible sur une ligne entière
    (h entier) ; sur une ligne demi-entière, la condition d'égalité
    (x+h)==y ne peut jamais être vraie (h non entier), donc "push"
    vaut 0.0 automatiquement -- pas besoin de le forcer explicitement,
    c'est une conséquence directe de la comparaison sur des nombres,
    vérifiée par test plutôt que supposée."""
    gain = _somme_cellules(matrice, lambda x, y: (x + h) > y)
    push = _somme_cellules(matrice, lambda x, y: (x + h) == y)
    perte = _somme_cellules(matrice, lambda x, y: (x + h) < y)
    return {"gain": gain, "push": push, "perte": perte}


def resultat_handicap(matrice, h):
    """
    Handicap domicile pour une ligne `h` quelconque (v3 §9.3).

    Ligne entière ou demi-entière (h*4 pair, ex. -1, -0.5, 0, 1.5) :
    lecture directe sur la matrice.

    Ligne au quart (h*4 impair, ex. -0.25, +0.25, -0.75) -- CORRECTIF
    12 : l'enjeu est divisé en deux moitiés égales sur les deux lignes
    demi-entières/entières adjacentes (h-0.25 et h+0.25, espacées de
    0.5 -- ex. -0.25 -> 0 et -0.5, cf. exemple du v3). Chaque moitié se
    règle indépendamment avec la formule ci-dessus ; le résultat global
    est la moyenne pondérée 50/50 des deux résultats. Aucune nouvelle
    formule de probabilité, seulement une règle de répartition de
    l'enjeu (le v3 le précise explicitement).
    """
    if matrice is None:
        return None

    h_quart_de_but = round(h * 4) % 2 != 0
    if not h_quart_de_but:
        return _resultat_handicap_ligne_entiere_ou_demie(matrice, h)

    ligne_basse = h - 0.25
    ligne_haute = h + 0.25
    r_bas = _resultat_handicap_ligne_entiere_ou_demie(matrice, ligne_basse)
    r_haut = _resultat_handicap_ligne_entiere_ou_demie(matrice, ligne_haute)
    return {
        "gain": 0.5 * r_bas["gain"] + 0.5 * r_haut["gain"],
        "push": 0.5 * r_bas["push"] + 0.5 * r_haut["push"],
        "perte": 0.5 * r_bas["perte"] + 0.5 * r_haut["perte"],
    }


DOUBLE_CHANCES_VALIDES = ("1X", "X2", "12")


def _condition_double_chance(cote_dc):
    if cote_dc == "1X":
        return lambda x, y: x >= y
    if cote_dc == "X2":
        return lambda x, y: x <= y
    if cote_dc == "12":
        return lambda x, y: x != y
    raise ValueError(f"cote_dc invalide : {cote_dc!r}, attendu un de {DOUBLE_CHANCES_VALIDES}")


def probabilite_combo_dc_total(matrice, cote_dc, ligne, sens):
    """
    Marché combiné Double Chance + Total de buts (v3 §9.4.3/9.4.4,
    famille COMBO_DC_TOTAL) -- résolu CONJOINTEMENT sur la matrice de
    scores, jamais par produit des deux probabilités marginales (DC et
    total ne sont pas indépendants, ils dépendent du même résultat).

    `cote_dc` : "1X", "X2" ou "12". `sens` : "over" ou "under".
    `ligne` en X.5 par construction du marché total.
    """
    if matrice is None:
        return None
    if sens not in ("over", "under"):
        raise ValueError(f"sens invalide : {sens!r}, attendu 'over' ou 'under'")

    condition_dc = _condition_double_chance(cote_dc)
    if sens == "over":
        condition_total = lambda x, y: (x + y) > ligne
    else:
        condition_total = lambda x, y: (x + y) < ligne

    return _somme_cellules(matrice, lambda x, y: condition_dc(x, y) and condition_total(x, y))


# Lignes IMPOSÉES par le v3 (pas un choix) :
LIGNES_BUTS_EQUIPE = (0.5, 1.5, 2.5)          # v3 §9.4.1/9.4.2, exact
LIGNES_COMBO_OVER = (1.5, 2.5, 3.5)           # v3 §9.4.3, exact
LIGNES_COMBO_UNDER = (1.5, 2.5, 3.5, 4.5)     # v3 §9.4.4, exact

# Lignes ASSUMÉES par défaut (le v3 donne la formule, pas une liste de lignes à
# calculer systématiquement pour Total/Handicap) -- décision du 08/09/2026,
# à ajuster si un usage réel demande d'autres lignes. Ne pas confondre avec les
# listes ci-dessus, qui elles sont imposées par le texte du v3.
LIGNES_TOTAL_PAR_DEFAUT = (0.5, 1.5, 2.5, 3.5, 4.5)
LIGNES_HANDICAP_PAR_DEFAUT = (-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5)


def calcule_tous_les_marches(lambda_a, lambda_b, max_buts=None):
    """
    Calcule TOUS les marchés couverts par ce module pour UN scénario λ
    donné (lambda_a, lambda_b) -- point d'entrée unique, réutilisé par
    archetype_model.main et archetype_model.backtest.boucle_b pour
    éviter que les deux dupliquent (et déphasent) la même logique.

    Si lambda_a ou lambda_b est None, chaque marché individuel renvoie
    déjà None par sa propre gestion de l'absent -- pas de garde
    spéciale nécessaire ici, le comportement se propage naturellement.
    """
    from . import distribution as _distribution  # import local : évite tout risque de cycle au chargement du package

    kwargs_matrice = {} if max_buts is None else {"max_buts": max_buts}
    matrice = _distribution.matrice_scores(lambda_a, lambda_b, **kwargs_matrice)
    dist_a = _distribution.distribution_marginale(lambda_a, **kwargs_matrice)
    dist_b = _distribution.distribution_marginale(lambda_b, **kwargs_matrice)

    return {
        "1x2": probabilites_1x2(matrice),
        "double_chance": probabilites_double_chance(matrice),
        "btts": probabilite_btts(matrice),
        "over_under_total": {
            ligne: probabilites_over_under_total(matrice, ligne) for ligne in LIGNES_TOTAL_PAR_DEFAUT
        },
        "handicap": {
            ligne: resultat_handicap(matrice, ligne) for ligne in LIGNES_HANDICAP_PAR_DEFAUT
        },
        "buts_equipe_domicile": {
            ligne: probabilites_buts_equipe(dist_a, ligne) for ligne in LIGNES_BUTS_EQUIPE
        },
        "buts_equipe_exterieur": {
            ligne: probabilites_buts_equipe(dist_b, ligne) for ligne in LIGNES_BUTS_EQUIPE
        },
        "combo_dc_total": {
            (dc, "over", ligne): probabilite_combo_dc_total(matrice, dc, ligne, "over")
            for dc in DOUBLE_CHANCES_VALIDES for ligne in LIGNES_COMBO_OVER
        } | {
            (dc, "under", ligne): probabilite_combo_dc_total(matrice, dc, ligne, "under")
            for dc in DOUBLE_CHANCES_VALIDES for ligne in LIGNES_COMBO_UNDER
        },
    }
