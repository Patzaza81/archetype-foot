"""
archetype_model/poisson/robustness.py — Robustesse multi-λ (ARCHETYPE_FOOT
v3, §8, CORRECTIF 2 et CORRECTIF 11) :

    écart-type des 4 probabilités (une par scénario λ) ≤ ROBUSTNESS_STD_THRESHOLD → STABLE
    écart-type > ROBUSTNESS_STD_THRESHOLD                                        → INSTABLE

`ROBUSTNESS_STD_THRESHOLD` est LA seule définition de ce seuil dans tout
le projet (CORRECTIF 11) -- ne jamais recopier 0.08 ailleurs, toujours
importer cette constante. Valeur de départ V1, non calibrée,
explicitement destinée à être révisée par walk-forward (jamais à
l'instinct) -- voir TRANSITION.md pour la procédure de calibration des
seuils non calibrés de ce projet.

DÉCISION DE CONCEPTION à ne pas re-deviner ailleurs, non dictée par le
v3 littéral : que faire si un des 4 scénarios est indisponible (λ=None
quelque part en amont, voir lambda_estimators.py) ? Calculer un
écart-type sur moins de 4 valeurs donnerait une fausse impression de
stabilité (un écart-type sur 1 ou 2 valeurs est mécaniquement plus
petit, donc plus souvent sous le seuil). Choix : si les 4 probabilités
ne sont pas TOUTES présentes, le statut est INDETERMINE (ni STABLE ni
INSTABLE) -- jamais un calcul dégradé silencieux qui fabriquerait une
fausse robustesse.

Réutilise `statistics.distributions.ecart_type` (même convention de
variance de POPULATION que le reste du projet, cohérence délibérée) --
pas de logique de dispersion dupliquée.
"""

from ..statistics.distributions import ecart_type as _ecart_type

ROBUSTNESS_STD_THRESHOLD = 0.08  # V1, non calibré, à réviser par walk-forward uniquement

STATUT_STABLE = "STABLE"
STATUT_INSTABLE = "INSTABLE"
STATUT_INDETERMINE = "INDETERMINE"


def evalue_robustesse(probabilites_scenarios):
    """
    `probabilites_scenarios` : les probabilités d'UN marché donné,
    une par scénario λ (offensif/défensif/contextuel/global, v3 §6) --
    exactement 4 valeurs attendues.

    Retourne {"ecart_type": float|None, "statut": STATUT_STABLE |
    STATUT_INSTABLE | STATUT_INDETERMINE}.

    INDETERMINE si moins de 4 valeurs, ou si l'une d'elles est None --
    voir décision de conception en tête de fichier.
    """
    if len(probabilites_scenarios) != 4 or any(p is None for p in probabilites_scenarios):
        return {"ecart_type": None, "statut": STATUT_INDETERMINE}

    et = _ecart_type(probabilites_scenarios)
    # Tolérance epsilon volontaire sur la comparaison au seuil : la règle v3 §8 est
    # "≤ ROBUSTNESS_STD_THRESHOLD", mais un écart-type mathématiquement égal au seuil
    # peut se représenter en flottant comme 0.08000000000000002 (imprécision de
    # représentation, pas une vraie dispersion supplémentaire) -- sans cette marge,
    # un cas pile au seuil serait classé INSTABLE par erreur de représentation binaire,
    # jamais par une différence réelle de dispersion. Trouvé par test avant livraison.
    statut = STATUT_STABLE if et <= ROBUSTNESS_STD_THRESHOLD + 1e-9 else STATUT_INSTABLE
    return {"ecart_type": et, "statut": statut}
