"""
archetype_model/h2h/h2h_markets.py — Statut CORROBORE / CONTREDIT /
NEUTRE / INSUFFISANT par marché (v3 §10).

Couvre TOUS les marchés (08/09/2026) : BTTS, Over/Under total, buts
par équipe (symétriques, faits en premier), et 1X2/Double Chance/
Handicap (asymétriques, faits ensuite -- voir plus bas pourquoi c'est
sûr).

POURQUOI 1X2/DC/HANDICAP SONT SÛRS ICI, alors que l'ancien moteur avait
un bug d'orientation dessus (TRANSITION.md, situation critique #17,
"Bug d'orientation H2H sur les marchés 1X2/Double chance dans
adapte_justification.py") : ce module ne lit JAMAIS les champs bruts
domicile_brut/exterieur_brut d'une confrontation passée. Il consomme
uniquement des confrontations déjà normalisées par
`h2h_stats.recupere_confrontations` -- {"buts_a", "buts_b"}, TOUJOURS
du point de vue de l'équipe A, peu importe si elle jouait à domicile
ou à l'extérieur dans CETTE rencontre historique précise. Comme A est
TOUJOURS l'équipe domicile du match analysé aujourd'hui (par
construction de tout ce pipeline), "buts_a > buts_b" veut dire
"domicile gagne AUJOURD'HUI" sans jamais avoir besoin de réinterpréter
un texte historique au moment de la comparaison -- c'est cette
réinterprétation tardive qui causait le bug de l'ancien moteur, et
elle n'existe plus dans cette architecture.

RÈGLE COMMUNE (`_compare`) : le modèle et la fréquence observée en H2H
doivent être du MÊME côté de 0.5 pour CORROBORER. Si l'un des deux (ou
les deux) est exactement à 0.5, le résultat est NEUTRE -- ambigu par
construction, jamais forcé arbitrairement vers un côté. S'applique
directement à Double Chance et Handicap (marchés à 2 issues, une fois
la bonne fréquence calculée). Pour 1X2 (3 issues), une règle dédiée
compare l'issue la plus fréquente en H2H à l'issue la plus probable du
modèle (`_argmax_unique`, voir plus bas).

RAPPEL (main.py) : pour l'instant, seul le scénario λ "offensif" (ou
celui choisi par l'appelant) doit être passé ici -- ce module ne sait
pas lequel des 4 scénarios est "le" scénario à comparer, il prend la
probabilité qu'on lui donne telle quelle. Le choix du scénario à
utiliser pour le H2H n'est pas encore câblé dans main.py (chantier
séparé, non fait ici).
"""

STATUT_CORROBORE = "CORROBORE"
STATUT_CONTREDIT = "CONTREDIT"
STATUT_NEUTRE = "NEUTRE"
STATUT_INSUFFISANT = "INSUFFISANT"

DOUBLE_CHANCES_VALIDES = ("1X", "X2", "12")
SELECTIONS_HANDICAP_VALIDES = ("domicile", "exterieur")


def _frequence(confrontations_retenues, predicat):
    """Fréquence de `predicat` parmi les confrontations retenues. None
    si la liste est vide (jamais un ZeroDivisionError)."""
    n = len(confrontations_retenues)
    if n == 0:
        return None
    return sum(1 for c in confrontations_retenues if predicat(c)) / n


def _compare(frequence_observee, probabilite_modele):
    """Compare la fréquence H2H observée à la probabilité du modèle --
    voir la règle commune dans le docstring de module."""
    if probabilite_modele == 0.5 or frequence_observee == 0.5:
        return STATUT_NEUTRE
    modele_favorable = probabilite_modele > 0.5
    h2h_favorable = frequence_observee > 0.5
    return STATUT_CORROBORE if modele_favorable == h2h_favorable else STATUT_CONTREDIT


def _argmax_unique(valeurs_par_issue):
    """Retourne l'issue (clé) dont la valeur est strictement la plus
    haute, ou None si égalité entre plusieurs issues -- jamais un choix
    arbitraire entre deux maximas ex æquo."""
    valeur_max = max(valeurs_par_issue.values())
    issues_au_max = [issue for issue, v in valeurs_par_issue.items() if v == valeur_max]
    return issues_au_max[0] if len(issues_au_max) == 1 else None


def evalue_btts(fenetre_h2h, probabilite_modele_oui):
    """`probabilite_modele_oui` : P(BTTS=oui) selon le modèle (v3 §6/§7,
    poisson.markets.probabilite_btts)."""
    if fenetre_h2h["palier"] == "INSUFFISANT":
        return STATUT_INSUFFISANT
    freq = _frequence(fenetre_h2h["confrontations_retenues"], lambda c: c["buts_a"] > 0 and c["buts_b"] > 0)
    return _compare(freq, probabilite_modele_oui)


def evalue_over_under_total(fenetre_h2h, ligne, probabilite_modele_over):
    """`probabilite_modele_over` : P(total > ligne) selon le modèle
    (poisson.markets.probabilites_over_under_total)."""
    if fenetre_h2h["palier"] == "INSUFFISANT":
        return STATUT_INSUFFISANT
    freq = _frequence(fenetre_h2h["confrontations_retenues"], lambda c: (c["buts_a"] + c["buts_b"]) > ligne)
    return _compare(freq, probabilite_modele_over)


def evalue_buts_equipe(fenetre_h2h, ligne, probabilite_modele_over, cote_equipe):
    """`cote_equipe` : "a" ou "b" -- le marché TEAM_GOALS porte sur UNE
    équipe précise, pas sur le match entier (v3 §9.4.1/9.4.2).
    `probabilite_modele_over` : P(buts de cette équipe > ligne) selon
    le modèle (poisson.markets.probabilites_buts_equipe)."""
    if cote_equipe not in ("a", "b"):
        raise ValueError(f"cote_equipe invalide : {cote_equipe!r}, attendu 'a' ou 'b'")
    if fenetre_h2h["palier"] == "INSUFFISANT":
        return STATUT_INSUFFISANT
    cle = "buts_a" if cote_equipe == "a" else "buts_b"
    freq = _frequence(fenetre_h2h["confrontations_retenues"], lambda c: c[cle] > ligne)
    return _compare(freq, probabilite_modele_over)


def evalue_1x2(fenetre_h2h, probabilites_modele_1x2):
    """
    `probabilites_modele_1x2` : {"domicile": ..., "nul": ..., "exterieur": ...}
    (poisson.markets.probabilites_1x2). A est TOUJOURS l'équipe
    domicile du match analysé -- "buts_a > buts_b" = victoire domicile.

    Compare l'issue la PLUS FRÉQUENTE en H2H à l'issue la PLUS PROBABLE
    selon le modèle -- CORROBORE si identique, CONTREDIT sinon. NEUTRE
    si l'un des deux camps (H2H ou modèle) n'a pas d'issue clairement
    dominante (égalité entre deux issues) -- jamais un choix forcé.
    """
    if fenetre_h2h["palier"] == "INSUFFISANT":
        return STATUT_INSUFFISANT
    confrontations = fenetre_h2h["confrontations_retenues"]
    n = len(confrontations)
    frequences_h2h = {
        "domicile": sum(1 for c in confrontations if c["buts_a"] > c["buts_b"]) / n,
        "nul": sum(1 for c in confrontations if c["buts_a"] == c["buts_b"]) / n,
        "exterieur": sum(1 for c in confrontations if c["buts_a"] < c["buts_b"]) / n,
    }
    issue_h2h = _argmax_unique(frequences_h2h)
    issue_modele = _argmax_unique(probabilites_modele_1x2)
    if issue_h2h is None or issue_modele is None:
        return STATUT_NEUTRE
    return STATUT_CORROBORE if issue_h2h == issue_modele else STATUT_CONTREDIT


def evalue_double_chance(fenetre_h2h, cote_dc, probabilite_modele):
    """
    `cote_dc` : "1X" (A ne perd pas), "X2" (A ne gagne pas), "12" (pas
    de nul). `probabilite_modele` : P de cette double chance selon le
    modèle (poisson.markets.probabilites_double_chance).
    """
    if cote_dc not in DOUBLE_CHANCES_VALIDES:
        raise ValueError(f"cote_dc invalide : {cote_dc!r}, attendu un de {DOUBLE_CHANCES_VALIDES}")
    if fenetre_h2h["palier"] == "INSUFFISANT":
        return STATUT_INSUFFISANT
    confrontations = fenetre_h2h["confrontations_retenues"]
    if cote_dc == "1X":
        freq = _frequence(confrontations, lambda c: c["buts_a"] >= c["buts_b"])
    elif cote_dc == "X2":
        freq = _frequence(confrontations, lambda c: c["buts_a"] <= c["buts_b"])
    else:  # "12"
        freq = _frequence(confrontations, lambda c: c["buts_a"] != c["buts_b"])
    return _compare(freq, probabilite_modele)


def evalue_handicap(fenetre_h2h, ligne, cote_selection, probabilite_modele):
    """
    `ligne` : ligne de handicap appliquée au DOMICILE (= A), comme dans
    poisson.markets.resultat_handicap. `cote_selection` : "domicile"
    (gain : (buts_a+ligne) > buts_b) ou "exterieur" (perte du point de
    vue domicile : (buts_a+ligne) < buts_b). `probabilite_modele` : la
    probabilité correspondante selon le modèle.

    Le push n'a pas de camp (ni gain ni perte pour aucun côté) -- il
    est exclu du calcul de fréquence des deux côtés, jamais compté pour
    l'un ou pour l'autre.
    """
    if cote_selection not in SELECTIONS_HANDICAP_VALIDES:
        raise ValueError(f"cote_selection invalide : {cote_selection!r}, attendu un de {SELECTIONS_HANDICAP_VALIDES}")
    if fenetre_h2h["palier"] == "INSUFFISANT":
        return STATUT_INSUFFISANT
    confrontations = fenetre_h2h["confrontations_retenues"]
    if cote_selection == "domicile":
        freq = _frequence(confrontations, lambda c: (c["buts_a"] + ligne) > c["buts_b"])
    else:
        freq = _frequence(confrontations, lambda c: (c["buts_a"] + ligne) < c["buts_b"])
    return _compare(freq, probabilite_modele)
