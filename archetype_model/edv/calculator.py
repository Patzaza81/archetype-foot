"""
archetype_model/edv/calculator.py — Edge et EDV (ARCHETYPE_FOOT v3,
§11.2), formules verrouillées :

    P_implicite = 1 / cote
    Edge = P_modele - P_implicite
    EDV  = P_modele * cote - 1

[CORRECTIF 3] Relation mathématique directe : EDV = cote * Edge. La
cote étant toujours positive, Edge et EDV ont TOUJOURS le même signe --
un seul filtre de candidature suffit (EDV>0 ⟺ Edge>0). Usage
différencié en aval (jamais ici) : Edge classe P1, EDV classe P2 (v3
§12).

Fonction PURE : prend une probabilité déjà calculée par le modèle
(poisson.markets) et une cote déjà récupérée par data.odds_provider,
ne recalcule ni l'une ni l'autre, ne modifie jamais la probabilité du
modèle (invariant explicite du v3, page 1 : "L'Edge et l'EDV ne
modifient jamais λ").

GESTION DE L'ABSENT : `probabilite_modele` peut être None (marché
indisponible en amont) et `cote` peut être None ou invalide (marché
non couvert par odds_provider, ou absent de precalcul.json) -- dans
les deux cas, Edge/EDV/P_implicite deviennent None, jamais une
exception, jamais une valeur inventée.
"""


def probabilite_implicite(cote):
    """1 / cote. None si `cote` est None, zéro ou négative -- une cote
    décimale réelle est toujours strictement positive (généralement
    >= 1.0), une valeur <= 0 est un signal de donnée invalide, jamais
    une vraie cote à diviser."""
    if cote is None or cote <= 0:
        return None
    return 1.0 / cote


def evalue_valeur(probabilite_modele, cote):
    """
    Retourne {"probabilite_implicite": ..., "edge": ..., "edv": ...}.

    Si `probabilite_modele` ou `cote` est invalide (None, ou cote<=0),
    les trois champs concernés par le calcul (edge, edv, et
    probabilite_implicite si la cote elle-même est invalide) sont
    None -- jamais un calcul partiel qui masquerait l'absence de
    donnée.
    """
    p_implicite = probabilite_implicite(cote)
    if probabilite_modele is None or p_implicite is None:
        return {"probabilite_implicite": p_implicite, "edge": None, "edv": None}

    edge = probabilite_modele - p_implicite
    edv = probabilite_modele * cote - 1.0
    return {"probabilite_implicite": p_implicite, "edge": edge, "edv": edv}
