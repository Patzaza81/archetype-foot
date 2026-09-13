"""
archetype_model/learning/contrefactuel.py — Test contre-factuel des seuils.

Pourquoi ce module existe : répond à "que se serait-il passé si ce
paramètre avait une autre valeur ?", en relisant l'archive résolue --
SANS jamais modifier la configuration active, l'archive ou la sélection
réelle. Le résultat est une SIMULATION, jamais une promotion --
validation.py et calibration.py (pas encore construits) décideront quoi
en faire, sous les garde-fous de garde_fous.py.

Portée actuelle, honnête : seuls EDV_MIN_* et COTE_MIN/COTE_MAX peuvent
être testés aujourd'hui, parce que ce sont les seuls paramètres pour
lesquels l'archive contient la donnée brute nécessaire (probabilite, edv,
cote -- via SELECTED et, depuis le correctif du 13/09/2026 sur
extraction.py, COUNTERFACTUAL). ROBUSTNESS_STD_THRESHOLD NE PEUT PAS être
testé : l'écart-type des 4 probabilités par scénario qui a produit le
statut STABLE/INSTABLE archivé n'est lui-même jamais conservé, seul le
statut l'est. tester_parametre() lève une erreur explicite pour ce
paramètre plutôt que de simuler sur une donnée absente.

Méthode pour EDV_MIN_* : reproduit EXACTEMENT
convergence._edv_min_requis() (brackets de probabilité 0.75/0.71/0.67/
0.63/0.60, FIXES -- décision de Patrick, 12/09/2026, jamais elles-mêmes
calibrables ici) pour déterminer quel enregistrement appartient au
bracket testé. Dans ce bracket : un SELECTED dont l'edv archivé tombe
sous la valeur proposée sortirait du portefeuille ; un COUNTERFACTUAL
dont l'edv archivé atteint la valeur proposée y entrerait. Les
enregistrements d'un autre bracket sont inchangés.

Méthode pour COTE_MIN/COTE_MAX : même principe, sur la cote archivée
directement -- un SELECTED hors du nouvel intervalle en sortirait, un
COUNTERFACTUAL rejeté pour COTE_HORS_INTERVALLE qui rentre dans le
nouvel intervalle y entrerait.

Ce module ne modifie JAMAIS l'archive, la configuration ou la sélection
réelle -- lecture seule, purement analytique.
"""

from __future__ import annotations

from typing import Any, NamedTuple

# Bracket de probabilité -> paramètre EDV_MIN calibrable correspondant.
# Reproduit EXACTEMENT convergence._edv_min_requis(), jamais réinventé.
_BRACKETS_EDV_MIN = (
    (0.75, "EDV_MIN_P_GE_75"),
    (0.71, "EDV_MIN_P_71_75"),
    (0.67, "EDV_MIN_P_67_71"),
    (0.63, "EDV_MIN_P_63_67"),
    (0.60, "EDV_MIN_P_60_63"),
)

PARAMETRES_EDV_MIN = frozenset(nom for _, nom in _BRACKETS_EDV_MIN)
PARAMETRES_COTE = frozenset({"COTE_MIN", "COTE_MAX"})
PARAMETRES_NON_TESTABLES = frozenset({"ROBUSTNESS_STD_THRESHOLD"})


def _bracket_edv_min(probabilite: float | None) -> str | None:
    if probabilite is None:
        return None
    for seuil, nom in _BRACKETS_EDV_MIN:
        if probabilite >= seuil:
            return nom
    return None


def bracket_edv_min(probabilite: float | None) -> str | None:
    """Version publique de _bracket_edv_min -- ajoutée le 13/09/2026 pour
    que le script d'orchestration nocturne puisse déterminer le bracket
    d'un enregistrement sans dupliquer cette logique. Comportement
    strictement identique, aucun changement de _bracket_edv_min."""
    return _bracket_edv_min(probabilite)


class ResultatContrefactuel(NamedTuple):
    parametre: str
    valeur_actuelle: float
    valeur_proposee: float
    nb_observations_actuelles: int
    nb_observations_contrefactuelles: int
    nb_gagnes_actuel: int
    nb_gagnes_contrefactuel: int
    roi_actuel: float | None
    roi_contrefactuel: float | None
    gain_roi: float | None


def _roi(somme_gains: float, n: int) -> float | None:
    return somme_gains / n if n > 0 else None


def _gain(record: dict[str, Any]) -> float | None:
    """mise = 1.0, identique à observations.calcule_gain_flat_stake --
    dupliqué ici volontairement pour ne pas faire dépendre contrefactuel.py
    de la forme des observations déjà agrégées, seulement des
    enregistrements bruts de l'archive."""
    resultat = record.get("resultat_marche")
    if resultat == "WIN":
        cote = record.get("cote")
        return (float(cote) - 1.0) if isinstance(cote, (int, float)) else None
    if resultat == "LOSS":
        return -1.0
    return None


def tester_parametre(
    parametre: str,
    valeur_actuelle: float,
    valeur_proposee: float,
    selections_resolues: list[dict[str, Any]],
    contrefactuels_resolus: list[dict[str, Any]],
) -> ResultatContrefactuel:
    """Simule le paramètre `parametre` à `valeur_proposee` au lieu de
    `valeur_actuelle`, à partir des enregistrements ARCHIVÉS ET RÉSOLUS
    (SELECTED d'une part, COUNTERFACTUAL d'autre part -- jamais les
    observations déjà agrégées par observations.py, qui ne portent pas
    edv_min_requis/motif_rejet). Ne modifie ni l'un ni l'autre.

    Lève ValueError si `parametre` n'est pas testable (ROBUSTNESS_STD_
    THRESHOLD) ou n'est pas reconnu -- jamais une simulation silencieuse
    sur un paramètre dont la donnée n'existe pas.
    """
    if parametre in PARAMETRES_NON_TESTABLES:
        raise ValueError(
            f"{parametre} ne peut pas être testé en contrefactuel : la "
            "donnée brute nécessaire (écart-type des 4 scénarios) n'est "
            "pas archivée, seul le statut STABLE/INSTABLE l'est."
        )
    if parametre in PARAMETRES_EDV_MIN:
        return _tester_edv_min(
            parametre, valeur_actuelle, valeur_proposee, selections_resolues, contrefactuels_resolus
        )
    if parametre in PARAMETRES_COTE:
        return _tester_cote(
            parametre, valeur_actuelle, valeur_proposee, selections_resolues, contrefactuels_resolus
        )
    raise ValueError(f"paramètre non reconnu par contrefactuel.py : {parametre!r}")


def _resultat(parametre, valeur_actuelle, valeur_proposee, n_actuel, g_actuel, somme_actuel, n_cf, g_cf, somme_cf):
    roi_actuel = _roi(somme_actuel, n_actuel)
    roi_cf = _roi(somme_cf, n_cf)
    return ResultatContrefactuel(
        parametre=parametre,
        valeur_actuelle=valeur_actuelle,
        valeur_proposee=valeur_proposee,
        nb_observations_actuelles=n_actuel,
        nb_observations_contrefactuelles=n_cf,
        nb_gagnes_actuel=g_actuel,
        nb_gagnes_contrefactuel=g_cf,
        roi_actuel=roi_actuel,
        roi_contrefactuel=roi_cf,
        gain_roi=(roi_cf - roi_actuel) if roi_actuel is not None and roi_cf is not None else None,
    )


def _tester_edv_min(parametre, valeur_actuelle, valeur_proposee, selections, contrefactuels):
    n_actuel = g_actuel = n_cf = g_cf = 0
    somme_actuel = somme_cf = 0.0

    for r in selections:
        gain = _gain(r)
        if gain is None:
            continue
        n_actuel += 1
        somme_actuel += gain
        g_actuel += 1 if r.get("resultat_marche") == "WIN" else 0

        # Reste dans le portefeuille contre-factuel SAUF si son bracket est
        # celui testé ET que son edv archivé tombe sous la valeur proposée.
        sort_du_portefeuille = (
            _bracket_edv_min(r.get("probabilite")) == parametre
            and isinstance(r.get("edv"), (int, float))
            and r["edv"] < valeur_proposee
        )
        if sort_du_portefeuille:
            continue
        n_cf += 1
        somme_cf += gain
        g_cf += 1 if r.get("resultat_marche") == "WIN" else 0

    for r in contrefactuels:
        gain = _gain(r)
        if gain is None:
            continue
        # N'entre dans le portefeuille contre-factuel QUE si son bracket
        # est celui testé ET que son edv archivé atteint la valeur proposée.
        entre_dans_portefeuille = (
            _bracket_edv_min(r.get("probabilite")) == parametre
            and isinstance(r.get("edv"), (int, float))
            and r["edv"] >= valeur_proposee
        )
        if not entre_dans_portefeuille:
            continue
        n_cf += 1
        somme_cf += gain
        g_cf += 1 if r.get("resultat_marche") == "WIN" else 0

    return _resultat(parametre, valeur_actuelle, valeur_proposee,
                      n_actuel, g_actuel, somme_actuel, n_cf, g_cf, somme_cf)


def _tester_cote(parametre, valeur_actuelle, valeur_proposee, selections, contrefactuels):
    def _dans_intervalle_propose(cote: float) -> bool:
        return cote >= valeur_proposee if parametre == "COTE_MIN" else cote <= valeur_proposee

    n_actuel = g_actuel = n_cf = g_cf = 0
    somme_actuel = somme_cf = 0.0

    for r in selections:
        gain = _gain(r)
        if gain is None:
            continue
        n_actuel += 1
        somme_actuel += gain
        g_actuel += 1 if r.get("resultat_marche") == "WIN" else 0

        cote = r.get("cote")
        if isinstance(cote, (int, float)) and _dans_intervalle_propose(cote):
            n_cf += 1
            somme_cf += gain
            g_cf += 1 if r.get("resultat_marche") == "WIN" else 0

    for r in contrefactuels:
        if r.get("motif_rejet") != "COTE_HORS_INTERVALLE":
            continue  # rejeté pour une autre raison -- n'entre jamais ici
        gain = _gain(r)
        if gain is None:
            continue
        cote = r.get("cote")
        if isinstance(cote, (int, float)) and _dans_intervalle_propose(cote):
            n_cf += 1
            somme_cf += gain
            g_cf += 1 if r.get("resultat_marche") == "WIN" else 0

    return _resultat(parametre, valeur_actuelle, valeur_proposee,
                      n_actuel, g_actuel, somme_actuel, n_cf, g_cf, somme_cf)
