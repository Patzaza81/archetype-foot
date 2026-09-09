"""
archetype_model/signals/convergence.py — Filtre de candidature (v3
§12.1), adapté d'un modèle fourni par Patrick le 09/09/2026, avec DEUX
corrections tranchées explicitement avant intégration :

1. ROBUSTESSE BINAIRE UNIQUEMENT (STABLE/INSTABLE) -- le modèle fourni
   prévoyait un troisième état "MODEREE" avec des règles renforcées.
   Supprimé, pas gardé en sommeil : `poisson/robustness.py` ne produit
   que STABLE/INSTABLE/INDETERMINE (seuil unique 0.08, v3 tel quel).
   Garder un chemin de code pour un état qui n'existe pas créerait une
   ambiguïté fonctionnelle (quelqu'un pourrait croire ce niveau
   opérationnel). Si la validation walk-forward démontre un jour
   qu'un niveau intermédiaire apporte quelque chose, ce sera un
   chantier à part -- modifier `robustness.py` ET ce fichier ensemble,
   jamais l'un sans l'autre.

2. AUCUN "SCÉNARIO RETENU" -- le v3 mentionne une fois (§9.4.1)
   "λ du scénario retenu" sans jamais le définir, et notre
   implémentation n'a jamais eu ce concept. Décision explicite de
   Patrick (09/09/2026) : PAS de scénario officiel choisi arbitrairement
   ni de moyenne des 4 -- le filtre tourne UNE FOIS PAR SCÉNARIO
   (offensif/défensif/contextuel/global) et exige l'ÉLIGIBILITÉ DANS
   LES 4 pour qu'un marché devienne candidat. Un seul échec = rejet
   global. Voir `filtre_marche_convergent` en bas de fichier -- c'est
   le point d'entrée à utiliser, PAS `filtre_marche` seule (gardée
   disponible pour un usage ponctuel sur un seul scénario si besoin,
   mais jamais utilisée seule pour décider d'un marché en production).

Responsabilité unique : décider si un marché déjà calculé peut
poursuivre le pipeline. Ne calcule ni λ, ni probabilité, ni robustesse,
ni cote, ni Edge, ni EDV -- les reçoit déjà calculés. Ne consulte
jamais le H2H, ne classe pas les marchés, ne dédoublonne pas et ne
sélectionne pas P1/P2/P3 (voir selection/, pas encore codé).

Pipeline (v3 §13) :
DONNEES -> MULTI-λ -> PROBABILITES -> ROBUSTESSE -> COTES -> EDGE/EDV
-> FILTRE (ce module) -> DEDOUBLONNAGE -> H2H (arbitre final) -> P1/P2/P3
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any, Mapping, Optional

from ..edv import calculator as edv_calculator

# ============================================================================
# PARAMETRES OPERATIONNELS
# ============================================================================

COTE_MIN = 1.26
COTE_MAX = 1.74

EDV_MIN_P_GE_75 = 0.05
EDV_MIN_P_71_75 = 0.05
EDV_MIN_P_67_71 = 0.07
EDV_MIN_P_63_67 = 0.10
EDV_MIN_P_60_63 = 0.12

STATUT_STABLE = "STABLE"
STATUT_INSTABLE = "INSTABLE"

SCENARIOS = ("offensif", "defensif", "contextuel", "global")


class Decision(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    REJETE = "REJETE"


class MotifRejet(str, Enum):
    DONNEES_INSUFFISANTES = "DONNEES_INSUFFISANTES"
    DONNEE_INVALIDE = "DONNEE_INVALIDE"
    PROBABILITE_INDISPONIBLE = "PROBABILITE_INDISPONIBLE"
    PROBABILITE_INVALIDE = "PROBABILITE_INVALIDE"
    PROBABILITE_TROP_FAIBLE = "PROBABILITE_TROP_FAIBLE"
    COTE_INVALIDE = "COTE_INVALIDE"
    COTE_HORS_INTERVALLE = "COTE_HORS_INTERVALLE"
    EDV_INDISPONIBLE = "EDV_INDISPONIBLE"
    EDV_INVALIDE = "EDV_INVALIDE"
    EDV_INSUFFISANTE = "EDV_INSUFFISANTE"
    ROBUSTESSE_INDISPONIBLE = "ROBUSTESSE_INDISPONIBLE"
    ROBUSTESSE_INVALIDE = "ROBUSTESSE_INVALIDE"
    ROBUSTESSE_INSUFFISANTE = "ROBUSTESSE_INSUFFISANTE"


@dataclass(frozen=True)
class ResultatFiltre:
    decision: Decision
    eligible: bool
    motif: Optional[str]
    niveau: Optional[str]
    probabilite_centrale: Optional[float]
    cote: Optional[float]
    edv: Optional[float]
    robustesse: Optional[str]
    marche: Optional[str]
    market_family: Optional[str]
    exposure_group: Optional[str]
    edv_min_requis: Optional[float]

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "eligible": self.eligible,
            "motif": self.motif,
            "niveau": self.niveau,
            "probabilite_centrale": self.probabilite_centrale,
            "cote": self.cote,
            "edv": self.edv,
            "robustesse": self.robustesse,
            "marche": self.marche,
            "market_family": self.market_family,
            "exposure_group": self.exposure_group,
            "edv_min_requis": self.edv_min_requis,
        }


def _nombre_fini(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(float(value))
    )


def _normalise_robustesse(value: Any) -> Optional[str]:
    """Reconnaît UNIQUEMENT STABLE/INSTABLE (voir décision 1 en tête de
    fichier). Tout le reste -- y compris "INDETERMINE", produit par
    poisson.robustness quand un scénario manque -- renvoie None, donc
    ROBUSTESSE_INVALIDE en aval : un marché dont la robustesse n'est
    pas clairement établie n'est jamais éligible."""
    if not isinstance(value, str):
        return None
    status = value.strip().upper()
    if status == STATUT_STABLE:
        return STATUT_STABLE
    if status == STATUT_INSTABLE:
        return STATUT_INSTABLE
    return None


def _edv_min_requis(probabilite: float) -> Optional[float]:
    """Retourne le seuil EDV correspondant à la probabilité centrale."""
    if probabilite >= 0.75:
        return EDV_MIN_P_GE_75
    if probabilite >= 0.71:
        return EDV_MIN_P_71_75
    if probabilite >= 0.67:
        return EDV_MIN_P_67_71
    if probabilite >= 0.63:
        return EDV_MIN_P_63_67
    if probabilite >= 0.60:
        return EDV_MIN_P_60_63
    return None


def _rejet(
    motif: MotifRejet,
    *,
    marche: Optional[str],
    market_family: Optional[str],
    exposure_group: Optional[str],
    probabilite: Optional[float],
    cote: Optional[float],
    edv: Optional[float],
    robustesse: Optional[str],
    edv_min_requis: Optional[float],
) -> ResultatFiltre:
    return ResultatFiltre(
        decision=Decision.REJETE,
        eligible=False,
        motif=motif.value,
        niveau=None,
        probabilite_centrale=probabilite,
        cote=cote,
        edv=edv,
        robustesse=robustesse,
        marche=marche,
        market_family=market_family,
        exposure_group=exposure_group,
        edv_min_requis=edv_min_requis,
    )


def filtre_marche(
    *,
    nombre_matchs: Any,
    probabilite_centrale: Any,
    cote: Any,
    edv: Any,
    robustesse: Any,
    marche: Optional[str] = None,
    market_family: Optional[str] = None,
    exposure_group: Optional[str] = None,
) -> ResultatFiltre:
    """
    Filtre UN marché pour UN scénario λ donné (voir
    `filtre_marche_convergent` pour le point d'entrée réel, qui exige
    l'unanimité des 4 scénarios -- cette fonction seule ne suffit
    jamais à décider qu'un marché est candidat en production).

    Règles :
      1. nombre de matchs utilisables >= 5 ;
      2. probabilité centrale valide et >= 60 % ;
      3. cote dans [1.26, 1.74] ;
      4. EDV >= seuil correspondant à P ;
      5. robustesse STABLE (INSTABLE ou toute autre valeur -> rejet).

    H2H n'est volontairement pas un paramètre de cette fonction (v3
    §12 : le H2H arbitre après le filtre, jamais avant, sauf la règle
    de contradiction forte -- non câblée ici, chantier séparé).
    """
    # 1 — Données
    if not _nombre_fini(nombre_matchs):
        return _rejet(
            MotifRejet.DONNEE_INVALIDE,
            marche=marche, market_family=market_family,
            exposure_group=exposure_group, probabilite=None,
            cote=None, edv=None, robustesse=None, edv_min_requis=None,
        )

    n = float(nombre_matchs)

    if n < 5 or n != int(n):
        return _rejet(
            MotifRejet.DONNEES_INSUFFISANTES if n < 5
            else MotifRejet.DONNEE_INVALIDE,
            marche=marche, market_family=market_family,
            exposure_group=exposure_group, probabilite=None,
            cote=None, edv=None, robustesse=None, edv_min_requis=None,
        )

    # 2 — Probabilité
    if probabilite_centrale is None:
        return _rejet(
            MotifRejet.PROBABILITE_INDISPONIBLE,
            marche=marche, market_family=market_family,
            exposure_group=exposure_group, probabilite=None,
            cote=None, edv=None, robustesse=None, edv_min_requis=None,
        )

    if not _nombre_fini(probabilite_centrale):
        return _rejet(
            MotifRejet.PROBABILITE_INVALIDE,
            marche=marche, market_family=market_family,
            exposure_group=exposure_group, probabilite=None,
            cote=None, edv=None, robustesse=None, edv_min_requis=None,
        )

    p = float(probabilite_centrale)

    if not 0.0 <= p <= 1.0:
        return _rejet(
            MotifRejet.PROBABILITE_INVALIDE,
            marche=marche, market_family=market_family,
            exposure_group=exposure_group, probabilite=p,
            cote=None, edv=None, robustesse=None, edv_min_requis=None,
        )

    edv_min = _edv_min_requis(p)

    if edv_min is None:
        return _rejet(
            MotifRejet.PROBABILITE_TROP_FAIBLE,
            marche=marche, market_family=market_family,
            exposure_group=exposure_group, probabilite=p,
            cote=None, edv=None, robustesse=None, edv_min_requis=None,
        )

    # 3 — Cote
    if not _nombre_fini(cote) or float(cote) <= 1.0:
        return _rejet(
            MotifRejet.COTE_INVALIDE,
            marche=marche, market_family=market_family,
            exposure_group=exposure_group, probabilite=p,
            cote=None, edv=None, robustesse=None, edv_min_requis=edv_min,
        )

    cote_value = float(cote)

    if not COTE_MIN <= cote_value <= COTE_MAX:
        return _rejet(
            MotifRejet.COTE_HORS_INTERVALLE,
            marche=marche, market_family=market_family,
            exposure_group=exposure_group, probabilite=p,
            cote=cote_value, edv=None, robustesse=None,
            edv_min_requis=edv_min,
        )

    # 4 — EDV
    if edv is None:
        return _rejet(
            MotifRejet.EDV_INDISPONIBLE,
            marche=marche, market_family=market_family,
            exposure_group=exposure_group, probabilite=p,
            cote=cote_value, edv=None, robustesse=None,
            edv_min_requis=edv_min,
        )

    if not _nombre_fini(edv):
        return _rejet(
            MotifRejet.EDV_INVALIDE,
            marche=marche, market_family=market_family,
            exposure_group=exposure_group, probabilite=p,
            cote=cote_value, edv=None, robustesse=None,
            edv_min_requis=edv_min,
        )

    edv_value = float(edv)

    if edv_value < edv_min:
        return _rejet(
            MotifRejet.EDV_INSUFFISANTE,
            marche=marche, market_family=market_family,
            exposure_group=exposure_group, probabilite=p,
            cote=cote_value, edv=edv_value, robustesse=None,
            edv_min_requis=edv_min,
        )

    # 5 — Robustesse (binaire uniquement, voir décision 1 en tête de fichier)
    status = _normalise_robustesse(robustesse)

    if robustesse is None:
        return _rejet(
            MotifRejet.ROBUSTESSE_INDISPONIBLE,
            marche=marche, market_family=market_family,
            exposure_group=exposure_group, probabilite=p,
            cote=cote_value, edv=edv_value, robustesse=None,
            edv_min_requis=edv_min,
        )

    if status is None:
        return _rejet(
            MotifRejet.ROBUSTESSE_INVALIDE,
            marche=marche, market_family=market_family,
            exposure_group=exposure_group, probabilite=p,
            cote=cote_value, edv=edv_value, robustesse=str(robustesse),
            edv_min_requis=edv_min,
        )

    if status == STATUT_INSTABLE:
        return _rejet(
            MotifRejet.ROBUSTESSE_INSUFFISANTE,
            marche=marche, market_family=market_family,
            exposure_group=exposure_group, probabilite=p,
            cote=cote_value, edv=edv_value, robustesse=status,
            edv_min_requis=edv_min,
        )

    # 6 — Eligible
    if p >= 0.75:
        niveau = "PREMIUM"
    elif p >= 0.71:
        niveau = "TRES_FORT"
    elif p >= 0.67:
        niveau = "FORT"
    elif p >= 0.63:
        niveau = "ELIGIBLE"
    else:
        niveau = "ELIGIBLE_PLUS"

    return ResultatFiltre(
        decision=Decision.ELIGIBLE,
        eligible=True,
        motif=None,
        niveau=niveau,
        probabilite_centrale=p,
        cote=cote_value,
        edv=edv_value,
        robustesse=status,
        marche=marche,
        market_family=market_family,
        exposure_group=exposure_group,
        edv_min_requis=edv_min,
    )


@dataclass(frozen=True)
class ResultatFiltreConvergent:
    """Résultat du filtre appliqué aux 4 scénarios (v3 §9.4.1 +
    décision du 09/09/2026 : aucun scénario officiel, unanimité
    requise)."""
    eligible: bool
    resultats_par_scenario: dict[str, ResultatFiltre]
    scenario_en_echec: Optional[str]  # premier scénario qui a échoué, None si éligible
    motif_rejet: Optional[str]  # motif du scenario_en_echec, None si éligible

    def as_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "resultats_par_scenario": {s: r.as_dict() for s, r in self.resultats_par_scenario.items()},
            "scenario_en_echec": self.scenario_en_echec,
            "motif_rejet": self.motif_rejet,
        }


def filtre_marche_convergent(
    *,
    nombre_matchs_par_scenario: Mapping[str, Any],
    probabilites_par_scenario: Mapping[str, Any],
    cote: Any,
    robustesse: Any,
    marche: Optional[str] = None,
    market_family: Optional[str] = None,
    exposure_group: Optional[str] = None,
) -> ResultatFiltreConvergent:
    """
    Point d'entrée réel du filtre (décision du 09/09/2026) : exécute
    `filtre_marche` UNE FOIS PAR SCÉNARIO (offensif/défensif/
    contextuel/global), avec la MÊME cote et la MÊME robustesse pour
    les 4 (la cote est une donnée de marché unique, la robustesse est
    déjà calculée sur l'ensemble des 4 scénarios par
    poisson.robustness -- ni l'une ni l'autre ne varie par scénario).
    L'EDV, en revanche, est recalculé PAR SCÉNARIO ici (même cote,
    probabilité différente par scénario -- edv.calculator.evalue_valeur).

    Un marché n'est ÉLIGIBLE que si les 4 scénarios le sont
    individuellement. Un seul échec -> rejet global, motif retenu =
    celui du PREMIER scénario en échec (ordre `SCENARIOS`), pour
    diagnostic -- mais tous les résultats par scénario restent
    disponibles dans `resultats_par_scenario`, aucun n'est masqué.

    `nombre_matchs_par_scenario`/`probabilites_par_scenario` : dicts
    indexés par les 4 noms de `SCENARIOS`. Un scénario absent de l'un
    ou l'autre dict est traité comme None (probabilité/N indisponible
    pour ce scénario -> ce scénario échoue le filtre, donc le marché
    entier est rejeté -- cohérent avec l'exigence d'unanimité).
    """
    resultats: dict[str, ResultatFiltre] = {}
    for scenario in SCENARIOS:
        n = nombre_matchs_par_scenario.get(scenario)
        p = probabilites_par_scenario.get(scenario)
        edv_scenario = edv_calculator.evalue_valeur(p, cote)["edv"] if p is not None else None
        resultats[scenario] = filtre_marche(
            nombre_matchs=n,
            probabilite_centrale=p,
            cote=cote,
            edv=edv_scenario,
            robustesse=robustesse,
            marche=marche,
            market_family=market_family,
            exposure_group=exposure_group,
        )

    scenario_en_echec = None
    for scenario in SCENARIOS:
        if not resultats[scenario].eligible:
            scenario_en_echec = scenario
            break

    return ResultatFiltreConvergent(
        eligible=scenario_en_echec is None,
        resultats_par_scenario=resultats,
        scenario_en_echec=scenario_en_echec,
        motif_rejet=None if scenario_en_echec is None else resultats[scenario_en_echec].motif,
    )
