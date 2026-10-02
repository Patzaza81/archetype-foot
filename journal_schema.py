"""Contrat de données du Journal comportemental.

Ce module est volontairement indépendant du moteur de décision V2.
Il décrit uniquement l'identité d'un match, les observations comportementales
et les observations de prix disponibles avant le coup d'envoi.

Le schéma est sérialisable en JSON sans dépendance externe.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = 1


class ContexteMarche(str, Enum):
    DOMICILE = "DOMICILE"
    EXTERIEUR = "EXTERIEUR"
    MATCH = "MATCH"


class RegimeComportement(str, Enum):
    INSUFFISANT = "INSUFFISANT"
    NEUTRE = "NEUTRE"
    EMERGENCE = "EMERGENCE"
    RENFORCEMENT = "RENFORCEMENT"
    RECURRENT = "RECURRENT"
    PERSISTANT = "PERSISTANT"
    AFFAIBLISSEMENT = "AFFAIBLISSEMENT"
    RUPTURE = "RUPTURE"
    REPRISE = "REPRISE"


class NiveauObservation(str, Enum):
    INSUFFISANT = "INSUFFISANT"
    FAIBLE = "FAIBLE"
    EXPLOITABLE = "EXPLOITABLE"
    SOLIDE = "SOLIDE"


class StatutAnticipation(str, Enum):
    EN_ATTENTE = "EN_ATTENTE"
    A_SURVEILLER = "A_SURVEILLER"
    COMPORTEMENT_CONFIRME = "COMPORTEMENT_CONFIRME"
    PRIX_A_ATTENDRE = "PRIX_A_ATTENDRE"
    PRIX_COMPATIBLE = "PRIX_COMPATIBLE"
    PRIX_NON_COMPATIBLE = "PRIX_NON_COMPATIBLE"


@dataclass(frozen=True)
class MatchIdentity:
    match_id: str
    date: str
    heure: str
    championnat: str
    saison: str
    equipe_domicile: str
    equipe_exterieure: str

    def __post_init__(self) -> None:
        if not self.match_id:
            raise ValueError("match_id est obligatoire")
        if not self.date:
            raise ValueError("date est obligatoire")
        if not self.championnat:
            raise ValueError("championnat est obligatoire")
        if not self.equipe_domicile or not self.equipe_exterieure:
            raise ValueError("les deux équipes sont obligatoires")


@dataclass
class MarcheObservation:
    marche: str
    equipe_reference: Optional[str] = None
    contexte: ContexteMarche = ContexteMarche.MATCH
    cote_tranche: Optional[str] = None
    resultat_historique: Optional[bool] = None
    echantillon: int = 0
    frequence: Optional[float] = None
    sequence_actuelle: List[str] = field(default_factory=list)
    regime_detecte: RegimeComportement = RegimeComportement.INSUFFISANT
    niveau_observation: NiveauObservation = NiveauObservation.INSUFFISANT

    def __post_init__(self) -> None:
        if not self.marche:
            raise ValueError("marche est obligatoire")
        if self.echantillon < 0:
            raise ValueError("echantillon ne peut pas être négatif")
        if self.frequence is not None and not 0.0 <= self.frequence <= 1.0:
            raise ValueError("frequence doit être comprise entre 0 et 1")


@dataclass
class CoteObservation:
    marche: str
    cote_observee: Optional[float] = None
    disponible: bool = False
    observee_le: Optional[str] = None
    prix_compatible: Optional[bool] = None

    def __post_init__(self) -> None:
        if not self.marche:
            raise ValueError("marche est obligatoire")
        if self.cote_observee is not None and self.cote_observee <= 1.0:
            raise ValueError("une cote décimale doit être > 1.0")


@dataclass
class FicheComportementaleMatch:
    identification: MatchIdentity
    observations_marches: Dict[str, MarcheObservation] = field(default_factory=dict)
    cotes: Dict[str, CoteObservation] = field(default_factory=dict)
    anticipation_globale: StatutAnticipation = StatutAnticipation.EN_ATTENTE
    niveau_observation: NiveauObservation = NiveauObservation.INSUFFISANT

    def to_dict(self) -> Dict[str, Any]:
        """Retourne une représentation JSON-compatible stable."""
        data = asdict(self)
        data["schema_version"] = SCHEMA_VERSION
        return _json_compatible(data)


def _json_compatible(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_compatible(item) for item in value]
    if isinstance(value, tuple):
        return [_json_compatible(item) for item in value]
    return value
