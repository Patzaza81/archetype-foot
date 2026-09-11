"""
archetype_model/justification.py — créé le 10/09/2026, à la demande
explicite de Patrick ("va jusqu'au bout"), pour remplacer les phrases
génériques ("confiance très forte") de l'affichage par des phrases
chiffrées et vraies ("7 des 8 derniers matchs...").

RÈGLE ABSOLUE, valable pour tout ce fichier :
- Ce module ne calcule AUCUNE probabilité, ne filtre AUCUN candidat, ne
  décide RIEN. Il est appelé une fois qu'archetype_model a déjà produit
  sa décision (candidat déjà passé le filtre 4/4, déjà sélectionné en
  P1/P2/P3) -- il ne fait que COMPTER, sur les mêmes matchs déjà chargés
  pour le calcul des lambdas (fenetres.A/B.matchs_retenus), combien
  d'entre eux confirment le pronostic déjà pris.
- Si le marché n'est pas encore couvert ici (ex. combos), la fonction
  renvoie None -- jamais un chiffre approximatif ou inventé. L'appelant
  doit alors afficher une phrase générique, pas un faux chiffre.
- "domicile"/"exterieur" ici veut dire : le rôle que l'équipe joue dans
  LE MATCH DU JOUR (l'équipe A est domicile aujourd'hui -> on regarde
  ses matchs passés À DOMICILE ; l'équipe B est extérieur aujourd'hui ->
  on regarde ses matchs passés À L'EXTÉRIEUR). C'est exactement la même
  convention que celle déjà utilisée par lambda_estimators.py pour les
  scénarios "offensif"/"défensif" (gf_a_domicile, ga_b_exterieur) --
  jamais une nouvelle convention inventée pour ce module.
"""

import re


def _filtre_role(matchs, domicile):
    """Sous-ensemble des matchs joués dans le rôle demandé (True=domicile,
    False=extérieur). matchs : liste de {"domicile": bool, "buts_marques":
    int, "buts_encaisses": int} -- même format que team_stats.py."""
    return [m for m in (matchs or []) if m.get("domicile") == domicile]


def _compte(matchs, condition):
    """Compte combien de matchs de la liste satisfont `condition` (une
    fonction match -> bool). Renvoie None si la liste est vide -- un
    échantillon de taille 0 ne confirme ni n'infirme rien, on ne doit
    jamais afficher 0/0."""
    n = len(matchs)
    if n == 0:
        return None
    confirmant = sum(1 for m in matchs if condition(m))
    return {"nb_confirmant": confirmant, "nb_echantillon": n}


def _combine(res_a, res_b):
    """Combine deux résultats de _compte (ex. domicile + extérieur pour
    un marché de buts total) en un seul comptage. None si les deux sont
    None ; sinon somme des deux échantillons disponibles."""
    if res_a is None and res_b is None:
        return None
    n = (res_a["nb_echantillon"] if res_a else 0) + (res_b["nb_echantillon"] if res_b else 0)
    c = (res_a["nb_confirmant"] if res_a else 0) + (res_b["nb_confirmant"] if res_b else 0)
    return {"nb_confirmant": c, "nb_echantillon": n}


def confirmation_historique(marche, matchs_a, matchs_b):
    """Calcule, pour la clé technique `marche` (celle produite par
    main.py, ex. "over_under_total_3.5_under"), combien des matchs
    RÉELLEMENT PASSÉS des deux équipes (déjà chargés pour le calcul des
    lambdas) auraient validé ce même pronostic.

    matchs_a : fenetres["A"]["matchs_retenus"] (l'équipe qui joue à
               domicile AUJOURD'HUI)
    matchs_b : fenetres["B"]["matchs_retenus"] (l'équipe qui joue à
               l'extérieur AUJOURD'HUI)

    Renvoie {"nb_confirmant": int, "nb_echantillon": int} ou None si ce
    marché n'est pas encore couvert par ce module, ou si l'échantillon
    disponible est vide.
    """
    dom_a = _filtre_role(matchs_a, True)
    ext_b = _filtre_role(matchs_b, False)

    if marche == "1x2_domicile":
        return _compte(dom_a, lambda m: m["buts_marques"] > m["buts_encaisses"])
    if marche == "1x2_exterieur":
        return _compte(ext_b, lambda m: m["buts_marques"] > m["buts_encaisses"])
    if marche == "1x2_nul":
        return _combine(
            _compte(dom_a, lambda m: m["buts_marques"] == m["buts_encaisses"]),
            _compte(ext_b, lambda m: m["buts_marques"] == m["buts_encaisses"]),
        )

    if marche == "double_chance_1X":
        return _compte(dom_a, lambda m: m["buts_marques"] >= m["buts_encaisses"])
    if marche == "double_chance_X2":
        return _compte(ext_b, lambda m: m["buts_marques"] >= m["buts_encaisses"])
    if marche == "double_chance_12":
        return _combine(
            _compte(dom_a, lambda m: m["buts_marques"] != m["buts_encaisses"]),
            _compte(ext_b, lambda m: m["buts_marques"] != m["buts_encaisses"]),
        )

    if marche == "btts_oui":
        return _combine(
            _compte(dom_a, lambda m: m["buts_marques"] > 0 and m["buts_encaisses"] > 0),
            _compte(ext_b, lambda m: m["buts_marques"] > 0 and m["buts_encaisses"] > 0),
        )
    if marche == "btts_non":
        return _combine(
            _compte(dom_a, lambda m: not (m["buts_marques"] > 0 and m["buts_encaisses"] > 0)),
            _compte(ext_b, lambda m: not (m["buts_marques"] > 0 and m["buts_encaisses"] > 0)),
        )

    if marche == "over_2_5":
        return _combine(
            _compte(dom_a, lambda m: m["buts_marques"] + m["buts_encaisses"] > 2.5),
            _compte(ext_b, lambda m: m["buts_marques"] + m["buts_encaisses"] > 2.5),
        )
    m_total = re.match(r"^over_under_total_(-?\d+(?:\.\d+)?)_(over|under)$", marche)
    if m_total:
        ligne = float(m_total.group(1))
        if m_total.group(2) == "over":
            cond = lambda m: m["buts_marques"] + m["buts_encaisses"] > ligne
        else:
            cond = lambda m: m["buts_marques"] + m["buts_encaisses"] < ligne
        return _combine(_compte(dom_a, cond), _compte(ext_b, cond))

    if marche == "cage_inviolee_domicile":
        return _compte(dom_a, lambda m: m["buts_encaisses"] == 0)
    if marche == "cage_inviolee_exterieur":
        return _compte(ext_b, lambda m: m["buts_encaisses"] == 0)
    if marche == "encaisse_domicile":
        return _compte(dom_a, lambda m: m["buts_encaisses"] > 0)
    if marche == "encaisse_exterieur":
        return _compte(ext_b, lambda m: m["buts_encaisses"] > 0)

    m_buts_dom = re.match(r"^buts_equipe_domicile_(-?\d+(?:\.\d+)?)_(over|under)$", marche)
    if m_buts_dom:
        ligne = float(m_buts_dom.group(1))
        cond = (lambda m: m["buts_marques"] > ligne) if m_buts_dom.group(2) == "over" else (lambda m: m["buts_marques"] < ligne)
        return _compte(dom_a, cond)
    m_buts_ext = re.match(r"^buts_equipe_exterieur_(-?\d+(?:\.\d+)?)_(over|under)$", marche)
    if m_buts_ext:
        ligne = float(m_buts_ext.group(1))
        cond = (lambda m: m["buts_marques"] > ligne) if m_buts_ext.group(2) == "over" else (lambda m: m["buts_marques"] < ligne)
        return _compte(ext_b, cond)

    if marche == "parite_pair":
        return _combine(
            _compte(dom_a, lambda m: (m["buts_marques"] + m["buts_encaisses"]) % 2 == 0),
            _compte(ext_b, lambda m: (m["buts_marques"] + m["buts_encaisses"]) % 2 == 0),
        )
    if marche == "parite_impair":
        return _combine(
            _compte(dom_a, lambda m: (m["buts_marques"] + m["buts_encaisses"]) % 2 == 1),
            _compte(ext_b, lambda m: (m["buts_marques"] + m["buts_encaisses"]) % 2 == 1),
        )

    m_hcp = re.match(r"^handicap_(domicile|exterieur)_(-?\d+(?:\.\d+)?)$", marche)
    if m_hcp:
        ligne = float(m_hcp.group(2))
        cond = lambda m: (m["buts_marques"] + ligne) > m["buts_encaisses"]
        return _compte(dom_a if m_hcp.group(1) == "domicile" else ext_b, cond)

    # combo_dc_total et tout marché non couvert ici : pas de chiffre --
    # jamais un chiffre approximatif ou une fausse combinaison des deux
    # conditions (le calcul conjoint correct nécessiterait de savoir si
    # les deux conditions se sont produites DANS LE MÊME match historique
    # pour chaque équipe séparément, ce que ce module simple ne fait pas
    # -- à traiter proprement dans un chantier dédié si besoin).
    return None
