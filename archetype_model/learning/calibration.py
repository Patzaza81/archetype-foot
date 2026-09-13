"""
archetype_model/learning/calibration.py — Orchestrateur de calibration
adaptative.

Pourquoi ce module existe : c'est le SEUL module autorisé à écrire dans
la configuration externe des paramètres calibrables, et il ne peut le
faire qu'après avoir fait passer une proposition par TOUTES les étapes
suivantes, dans cet ordre, jamais court-circuitées :

    garde_fous.autoriser_promotion() (taille, amplitude, dérive, liste
                                       fermée -- rejette au premier motif)
        -> validation.valide_hors_echantillon() (apprentissage +
                                                   hors échantillon)
        -> PROMOTION ou REJET
        -> journal.enregistrer_promotion() (toujours, promu ou rejeté)

Les garde-fous passent AVANT la validation hors échantillon
volontairement : aucune raison de lancer un contrefactuel coûteux sur une
proposition déjà hors des limites de sécurité (taille d'échantillon,
amplitude par cycle, dérive cumulée).

Ce module n'appelle, ne modifie et n'importe JAMAIS selector.py,
convergence.py ou deduplication.py. Il écrit uniquement dans
config/adaptive_parameters.json et config/adaptive_state.json, via les
fonctions de ce fichier -- jamais un accès disque direct ailleurs dans le
projet.

IMPORTANT, à ne jamais perdre de vue : à ce stade (13/09/2026),
convergence.py continue de lire ses seuils comme des constantes Python
codées en dur -- il NE LIT PAS ENCORE config/adaptive_parameters.json.
Ce module peut donc calculer des propositions et même les "promouvoir"
(écrire dans le fichier de configuration), mais TANT QUE convergence.py
n'est pas modifié pour lire ce fichier, rien de tout cela n'a le moindre
effet sur la sélection réelle. C'est un choix délibéré : brancher
calibration.py sur convergence.py est un chantier séparé, qui touche pour
la première fois un fichier jusqu'ici jamais modifié, et qui doit être
validé explicitement avant d'être fait.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from archetype_model.learning import garde_fous, journal, validation

FICHIER_PARAMETRES_DEFAUT = "config/adaptive_parameters.json"
FICHIER_ETAT_DEFAUT = "config/adaptive_state.json"


class CalibrationError(Exception):
    """Erreur fonctionnelle explicite de l'orchestrateur de calibration."""


def _lire_json(chemin: str) -> dict[str, Any] | None:
    path = Path(chemin)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _ecrire_json_atomique(chemin: str, contenu: dict[str, Any]) -> None:
    path = Path(chemin)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(contenu, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def charger_parametres(chemin: str = FICHIER_PARAMETRES_DEFAUT) -> dict[str, Any]:
    """Lève une erreur explicite si le fichier n'existe pas -- jamais de
    valeurs par défaut inventées silencieusement pour un fichier de
    configuration absent."""
    contenu = _lire_json(chemin)
    if contenu is None:
        raise CalibrationError(
            f"{chemin} introuvable -- doit être créé (valeurs initiales) "
            "avant tout cycle de calibration."
        )
    return contenu


def charger_etat(chemin: str = FICHIER_ETAT_DEFAUT) -> dict[str, Any]:
    """Contrairement aux paramètres, un état absent est normal au tout
    premier cycle -- retourne un état vide plutôt qu'une erreur."""
    contenu = _lire_json(chemin)
    if contenu is None:
        return {"version_active": 0, "date_activation": None, "parametres": {}, "dernier_cycle": None}
    return contenu


def evaluer_proposition(
    parametre: str,
    valeur_actuelle: float,
    valeur_origine: float,
    valeur_proposee: float,
    nb_observations_resolues: int,
    selections_resolues: list[dict[str, Any]],
    contrefactuels_resolus: list[dict[str, Any]],
) -> dict[str, Any]:
    """Fait passer UNE proposition par toute la chaîne de décision, sans
    rien écrire sur disque -- une simple évaluation, jamais une action.

    Retourne toujours un dict avec au moins "decision" ("PROMU" ou
    "REJETE"), "motif" et "etape" (celle qui a décidé) -- jamais un
    verdict silencieux.
    """
    verdict_garde_fou = garde_fous.autoriser_promotion(
        parametre, nb_observations_resolues, valeur_origine, valeur_actuelle, valeur_proposee
    )
    if not verdict_garde_fou.autorise:
        return {
            "decision": "REJETE",
            "motif": verdict_garde_fou.motif,
            "etape": "garde_fous",
            "validation": None,
        }

    resultat_validation = validation.valide_hors_echantillon(
        parametre, valeur_actuelle, valeur_proposee, selections_resolues, contrefactuels_resolus
    )
    if not resultat_validation["ameliore_les_deux_zones"]:
        return {
            "decision": "REJETE",
            "motif": "n'améliore pas simultanément la zone d'apprentissage et la zone hors échantillon",
            "etape": "validation",
            "validation": resultat_validation,
        }

    return {
        "decision": "PROMU",
        "motif": "garde-fous respectés, amélioration confirmée sur les deux zones",
        "etape": "promotion",
        "validation": resultat_validation,
    }


def promouvoir(
    parametre: str,
    nouvelle_valeur: float,
    date_cycle: str,
    evidence: dict[str, Any] | None = None,
    chemin_parametres: str = FICHIER_PARAMETRES_DEFAUT,
    chemin_etat: str = FICHIER_ETAT_DEFAUT,
    chemin_journal_promotion: str = "config/journal_promotion.jsonl",
) -> None:
    """Écrit RÉELLEMENT la nouvelle valeur dans la configuration active.
    À appeler UNIQUEMENT après un verdict "PROMU" de evaluer_proposition()
    -- cette fonction ne revérifie pas les garde-fous elle-même, elle
    exécute une décision déjà prise, elle ne la prend pas.

    Toujours journalisée, même en cas d'erreur d'écriture (auquel cas
    l'exception remonte -- jamais une promotion silencieusement à moitié
    faite)."""
    parametres = charger_parametres(chemin_parametres)
    bloc = parametres.get("parametres", {})
    if parametre not in bloc:
        raise CalibrationError(
            f"{parametre} absent de {chemin_parametres} -- impossible de "
            "promouvoir un paramètre qui n'existe pas dans la "
            "configuration active."
        )

    ancienne_valeur = bloc[parametre]["valeur"]
    bloc[parametre]["valeur"] = nouvelle_valeur
    _ecrire_json_atomique(chemin_parametres, parametres)

    etat = charger_etat(chemin_etat)
    etat.setdefault("parametres", {})[parametre] = {
        "valeur_active": nouvelle_valeur,
        "valeur_origine": bloc[parametre].get("valeur_origine", nouvelle_valeur),
    }
    etat["dernier_cycle"] = date_cycle
    etat["version_active"] = etat.get("version_active", 0) + 1
    etat["date_activation"] = date_cycle
    _ecrire_json_atomique(chemin_etat, etat)

    journal.enregistrer_promotion(chemin_journal_promotion, {
        "date_cycle": date_cycle,
        "parametre": parametre,
        "avant": ancienne_valeur,
        "apres": nouvelle_valeur,
        "decision": "PROMU",
        "evidence": evidence or {},
    })


def rejeter(
    parametre: str,
    valeur_actuelle: float,
    valeur_proposee: float,
    date_cycle: str,
    motif: str,
    chemin_journal_promotion: str = "config/journal_promotion.jsonl",
) -> None:
    """Journalise un rejet -- n'écrit JAMAIS dans la configuration active.
    Un rejet doit être tracé au même titre qu'une promotion (répond aussi
    à "pourquoi ce seuil n'a-t-il PAS changé ?")."""
    journal.enregistrer_promotion(chemin_journal_promotion, {
        "date_cycle": date_cycle,
        "parametre": parametre,
        "avant": valeur_actuelle,
        "apres": valeur_actuelle,
        "decision": "REJETE",
        "evidence": {"motif": motif},
    })
