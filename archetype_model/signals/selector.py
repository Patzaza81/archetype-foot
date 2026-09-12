"""
archetype_model/signals/selector.py — Sélection P1/P2/P3 (ARCHETYPE_FOOT
v3, §12.3), moteur de DÉCISION FINAL -- ne recalcule rien. Reçoit
uniquement des candidats déjà : filtrés (signals.convergence, unanimité
des 4 scénarios), dédoublonnés (signals.deduplication, un par famille
ET par groupe d'exposition), robustes (STABLE, garanti par le filtre
en amont).

CASCADE P1 (meilleure convergence), décision de Patrick (09/09/2026),
dans cet ordre -- s'arrête au premier critère qui différencie, jamais
une addition/pondération (même principe que dedup, CORRECTIF 9) :
    1. niveau d'éligibilité (PREMIUM > TRES_FORT > FORT > ELIGIBLE >
       ELIGIBLE_PLUS, tel que produit par signals.convergence) ;
    2. robustesse STABLE (no-op en pratique -- tous les candidats
       reçus ici sont déjà STABLE par construction du filtre en
       amont, gardé pour fidélité à la cascade telle qu'écrite) ;
    3. qualité du signal Statistiques (favorable > neutre >
       défavorable, puis fréquence à égalité de direction -- DÉCISION
       DE CONCEPTION non donnée littéralement par le v3, documentée
       ici comme telle) ;
    4. fiabilité H2H (TRES_FIABLE > FIABLE > INDICATIF > INSUFFISANT)
       -- UNIQUEMENT pour départager des candidats déjà équivalents
       sur 1-3, jamais pour faire passer un candidat devant un autre
       qui le bat sur un critère précédent ;
    5. EDV décroissant, dernier départage économique.

P2 (diversification) : le meilleur candidat restant (même cascade)
dont la market_family ET l'exposure_group diffèrent TOUS LES DEUX de
P1. None si aucun candidat ne satisfait cette double condition --
jamais un remplissage forcé.

P3 (bonus, strictement optionnel) : le meilleur candidat restant dont
la famille ET le groupe diffèrent à la fois de P1 ET de P2, ET qui est
STABLE avec un EDV strictement positif (déjà garanti par le filtre en
amont pour tout candidat éligible -- revérifié ici explicitement par
fidélité au v3, pas parce qu'un candidat pourrait échouer ce test).
None si aucun ne qualifie -- "P3 = aucun" est un résultat normal, pas
une erreur (v3 §12.3, CORRECTIF 10).

H2H RESTE UN DÉPARTAGE, JAMAIS UN FILTRE (rappel, cohérent avec
signals.deduplication) : aucune fonction ici n'élimine un candidat sur
la seule base du H2H -- le palier H2H n'intervient qu'au rang 4 de la
cascade P1 (et implicitement dans P2/P3 qui réutilisent la même
cascade), jamais avant ni en dehors de ce rang.

STRUCTURE D'ENTRÉE ATTENDUE : chaque candidat est un dict portant au
minimum "market_family", "exposure_group", "niveau", "robustesse",
"edv", "h2h_palier", "signal_direction", "signal_frequence" -- tous
déjà calculés en amont (convergence, deduplication, h2h_stats,
statistiques_signal). Ce module ne lit que ces champs, n'en calcule
aucun.
"""

ORDRE_NIVEAU = {"PREMIUM": 4, "TRES_FORT": 3, "FORT": 2, "ELIGIBLE": 1, "ELIGIBLE_PLUS": 0}
ORDRE_ROBUSTESSE = {"STABLE": 1, "INSTABLE": 0}
ORDRE_DIRECTION_SIGNAL = {"favorable": 2, "neutre": 1, "defavorable": 0}
ORDRE_PALIER_H2H = {"TRES_FIABLE": 3, "FIABLE": 2, "INDICATIF": 1, "INSUFFISANT": 0}


def _cle_cascade(candidat):
    """Clé de comparaison pour la cascade P1 (voir docstring de
    module). Valeurs absentes ou inconnues traitées comme le rang le
    plus bas -- jamais une exception sur un candidat mal formé."""
    niveau = ORDRE_NIVEAU.get(candidat.get("niveau"), -1)
    robustesse = ORDRE_ROBUSTESSE.get(candidat.get("robustesse"), 0)

    direction = ORDRE_DIRECTION_SIGNAL.get(candidat.get("signal_direction"), -1)
    frequence = candidat.get("signal_frequence")
    qualite_signal = (direction, frequence if frequence is not None else float("-inf"))

    h2h = ORDRE_PALIER_H2H.get(candidat.get("h2h_palier"), 0)

    edv = candidat.get("edv")
    edv_valeur = edv if edv is not None else float("-inf")

    return (niveau, robustesse, qualite_signal, h2h, edv_valeur)


def selectionner_p1(candidats):
    """Le meilleur candidat selon la cascade complète. None si
    `candidats` est vide -- jamais une exception ni un choix forcé."""
    if not candidats:
        return None
    return max(candidats, key=_cle_cascade)


def selectionner_p2(candidats, p1):
    """Le meilleur candidat restant dont la famille ET le groupe
    d'exposition diffèrent TOUS LES DEUX de P1 (diversification
    obligatoire, v3 §12.3). None si P1 est None ou si aucun candidat
    ne satisfait cette double condition."""
    if p1 is None:
        return None
    eligibles = [
        c for c in candidats
        if c is not p1
        and c["market_family"] != p1["market_family"]
        and c["exposure_group"] != p1["exposure_group"]
    ]
    if not eligibles:
        return None
    return max(eligibles, key=_cle_cascade)


def selectionner_p3(candidats, p1, p2):
    """Le meilleur candidat restant dont la famille ET le groupe
    diffèrent à la fois de P1 ET de P2, STABLE, EDV strictement
    positif. None si P1 ou P2 est None, ou si aucun candidat ne
    qualifie -- "aucun P3" est un résultat normal (CORRECTIF 10),
    jamais un remplissage forcé."""
    if p1 is None or p2 is None:
        return None
    eligibles = [
        c for c in candidats
        if c is not p1 and c is not p2
        and c["market_family"] not in (p1["market_family"], p2["market_family"])
        and c["exposure_group"] not in (p1["exposure_group"], p2["exposure_group"])
        and c.get("robustesse") == "STABLE"
        and c.get("edv") is not None and c.get("edv") > 0
    ]
    if not eligibles:
        return None
    return max(eligibles, key=_cle_cascade)


def selectionner(candidats):
    """Orchestrateur : calcule P1, puis P2 (à partir de P1), puis P3
    (à partir de P1 et P2). Retourne {"P1": ..., "P2": ..., "P3": ...}
    -- chaque valeur peut être None (voir les fonctions individuelles
    pour les conditions exactes)."""
    p1 = selectionner_p1(candidats)
    p2 = selectionner_p2(candidats, p1)
    p3 = selectionner_p3(candidats, p1, p2)
    return {"P1": p1, "P2": p2, "P3": p3}


# ============================================================================
# DIAGNOSTIC DE DIFFÉRENCIATION (chantier du 12/09/2026, demande de Patrick :
# "la vraie raison du choix", pas une phrase reconstituée) -- PUREMENT
# DIAGNOSTIC, appelé UNIQUEMENT APRÈS que selectionner_p1/p2/p3 ont déjà
# figé leur résultat. Ne modifie, ne relit ni ne recalcule RIEN de la
# sélection elle-même -- aucune des fonctions ci-dessus n'est touchée,
# aucune d'elles n'appelle ce qui suit. Sert uniquement à expliquer, après
# coup, quel critère de la cascade a réellement différencié le gagnant du
# meilleur concurrent resté sur le carreau -- pour que justification.py
# puisse écrire une phrase vraie au lieu d'une phrase plausible.
#
# PRINCIPE DE SÉCURITÉ : les pools de concurrents ci-dessous (fonctions
# diagnostique_p1/p2/p3) REPRODUISENT EXACTEMENT les conditions
# d'éligibilité déjà écrites dans selectionner_p2/selectionner_p3
# ci-dessus (copié tel quel, jamais réinventé) -- si ces conditions
# changent un jour, ces trois fonctions doivent être mises à jour en
# même temps, jamais l'une sans l'autre.
# ============================================================================

NOMS_CRITERES_CASCADE = ("niveau", "robustesse", "signal", "h2h", "edv")


def _decompose_cle(candidat):
    """Les 5 composantes de _cle_cascade, dans l'ordre, nommées pour
    comparaison critère par critère -- jamais utilisé pour trier."""
    return _cle_cascade(candidat)


def diagnostique_differenciation(gagnant, concurrents):
    """
    Détermine, PARMI LES CANDIDATS RÉELLEMENT CONSIDÉRÉS pour ce rang
    (`concurrents`, sans le gagnant), lequel des 5 critères de la
    cascade (niveau, robustesse, signal, h2h, edv) a réellement
    différencié `gagnant` du meilleur concurrent restant.

    Ne participe à aucune sélection, ne modifie aucun candidat.

    Retourne toujours un dict avec au moins la clé "critere" :
        {"critere": "aucune_selection"} -- `gagnant` est None
        {"critere": "aucun_concurrent"} -- aucun concurrent dans le pool
        {"critere": "egalite_totale"} -- meilleur concurrent identique
            sur les 5 critères (rare, mais rapporté honnêtement si ça
            arrive -- jamais masqué derrière un faux départage)
        {"critere": <un des 5 noms>, "valeur_gagnant": ...,
         "valeur_concurrent": ...} -- le premier critère, DANS L'ORDRE
            DE LA CASCADE, où gagnant et meilleur concurrent diffèrent.

    `concurrents` : les autres candidats du MÊME pool que celui qui a
    produit `gagnant` (fourni par l'appelant, jamais recalculé ici).
    """
    if gagnant is None:
        return {"critere": "aucune_selection"}
    if not concurrents:
        return {"critere": "aucun_concurrent"}

    meilleur_concurrent = max(concurrents, key=_cle_cascade)
    cle_gagnant = _decompose_cle(gagnant)
    cle_concurrent = _decompose_cle(meilleur_concurrent)

    for nom, valeur_gagnant, valeur_concurrent in zip(
        NOMS_CRITERES_CASCADE, cle_gagnant, cle_concurrent
    ):
        if valeur_gagnant != valeur_concurrent:
            return {
                "critere": nom,
                "valeur_gagnant": valeur_gagnant,
                "valeur_concurrent": valeur_concurrent,
            }
    return {"critere": "egalite_totale"}


def diagnostique_p1(candidats, p1):
    """Diagnostic pour P1 -- concurrents = tout le pool passé à
    selectionner_p1 (candidats dédoublonnés), sans P1 lui-même."""
    if p1 is None:
        return {"critere": "aucune_selection"}
    concurrents = [c for c in candidats if c is not p1]
    return diagnostique_differenciation(p1, concurrents)


def diagnostique_p2(candidats, p1, p2):
    """Diagnostic pour P2 -- MÊME condition d'éligibilité que
    selectionner_p2 (copiée à l'identique, voir avertissement de
    section)."""
    if p2 is None:
        return {"critere": "aucune_selection"}
    concurrents = [
        c for c in candidats
        if c is not p2 and c is not p1
        and c["market_family"] != p1["market_family"]
        and c["exposure_group"] != p1["exposure_group"]
    ]
    return diagnostique_differenciation(p2, concurrents)


def diagnostique_p3(candidats, p1, p2, p3):
    """Diagnostic pour P3 -- MÊME condition d'éligibilité que
    selectionner_p3 (copiée à l'identique, voir avertissement de
    section)."""
    if p3 is None:
        return {"critere": "aucune_selection"}
    concurrents = [
        c for c in candidats
        if c is not p3 and c is not p1 and c is not p2
        and c["market_family"] not in (p1["market_family"], p2["market_family"])
        and c["exposure_group"] not in (p1["exposure_group"], p2["exposure_group"])
        and c.get("robustesse") == "STABLE"
        and c.get("edv") is not None and c.get("edv") > 0
    ]
    return diagnostique_differenciation(p3, concurrents)


def diagnostique_selection(candidats, selection):
    """Calcule le diagnostic des 3 rangs à partir du résultat déjà figé
    de `selectionner()` -- appelée APRÈS coup, jamais pendant la
    sélection. `selection` : le dict {"P1":..., "P2":..., "P3":...}
    déjà produit par selectionner(candidats)."""
    p1, p2, p3 = selection.get("P1"), selection.get("P2"), selection.get("P3")
    return {
        "P1": diagnostique_p1(candidats, p1),
        "P2": diagnostique_p2(candidats, p1, p2),
        "P3": diagnostique_p3(candidats, p1, p2, p3),
    }
