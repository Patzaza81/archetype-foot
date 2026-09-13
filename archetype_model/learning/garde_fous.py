"""
archetype_model/learning/garde_fous.py — Barrière de sécurité.

Pourquoi ce module existe : calibration.py (pas encore construit) ne doit
JAMAIS pouvoir promouvoir un ajustement de paramètre calibrable sans passer
par cette barrière -- c'est elle qui empêche le système de sur-ajuster sur
du bruit statistique ou de dériver sans limite (cahier des charges v2 §6,
réponse du bureau d'étude aux Questions 1 et 3, Addendum 2).

Valeurs de départ PROPOSÉES par le bureau d'étude le 12/09/2026 et jamais
challengées depuis sur données réelles -- même statut que
ROBUSTNESS_STD_THRESHOLD : une constante n'est pas calibrée tant que
personne ne l'a vérifiée en production. À réviser si l'expérience le
justifie, jamais à modifier ici sans une décision explicite documentée.

Ce module est PUREMENT DÉCISIONNEL : aucune lecture ni écriture de fichier.
calibration.py et journal.py restent responsables de l'état
(config/adaptive_state.json, pas encore construit) ; garde_fous.py se
contente de répondre OUI/NON à une proposition, avec le motif exact du
refus.

Frontière non négociable (Addendum 2, Décision 4) : ce module ne peut
JAMAIS autoriser l'ajout d'un nouveau paramètre calibrable -- seule la
valeur d'un paramètre DÉJÀ dans PARAMETRES_CALIBRABLES peut être ajustée.
Étendre cette liste est une décision humaine documentée, jamais un effet
de bord de ce module.
"""

from __future__ import annotations

from typing import NamedTuple

# Liste fermée des paramètres calibrables (cahier des charges v2 §2.4,
# Addendum 2 Décision 3) -- jamais étendue ici, jamais par le système lui-même.
PARAMETRES_CALIBRABLES = frozenset({
    "COTE_MIN",
    "COTE_MAX",
    "ROBUSTNESS_STD_THRESHOLD",
    "EDV_MIN_P_GE_75",
    "EDV_MIN_P_71_75",
    "EDV_MIN_P_67_71",
    "EDV_MIN_P_63_67",
    "EDV_MIN_P_60_63",
})

# Garde-fous renforcés pour COTE_MIN/COTE_MAX (Addendum 2, section 1) --
# ils déterminent directement le profil de risque de CHAQUE pari du système.
PARAMETRES_A_GARDE_FOUS_RENFORCES = frozenset({"COTE_MIN", "COTE_MAX"})

TAILLE_MIN_STANDARD = 50
TAILLE_MIN_RENFORCEE = 100
AMPLITUDE_MAX_STANDARD = 0.05        # +/-5 % de la valeur courante par cycle
AMPLITUDE_MAX_RENFORCEE = 0.02       # +/-2 % pour COTE_MIN/COTE_MAX
DERIVE_MAX_STANDARD = 0.15           # +/-15 % cumulé par rapport à l'origine
DERIVE_MAX_RENFORCEE = 0.08          # +/-8 % pour COTE_MIN/COTE_MAX
SEUIL_ROLLBACK_DEGRADATION = 0.10    # dégradation de ROI déclenchant un retour arrière


class VerdictGardeFou(NamedTuple):
    """autorise=False signifie un refus (ou, pour verifier_rollback, qu'un
    retour arrière est nécessaire). motif est toujours vide quand autorise
    est True."""
    autorise: bool
    motif: str


def _est_renforce(parametre: str) -> bool:
    return parametre in PARAMETRES_A_GARDE_FOUS_RENFORCES


def verifier_parametre_autorise(parametre: str) -> VerdictGardeFou:
    """Premier verrou, absolu : le paramètre doit déjà exister dans la liste
    fermée -- jamais un paramètre inventé, jamais une extension silencieuse
    de PARAMETRES_CALIBRABLES."""
    if parametre not in PARAMETRES_CALIBRABLES:
        return VerdictGardeFou(False, f"paramètre non calibrable : {parametre!r}")
    return VerdictGardeFou(True, "")


def verifier_taille_echantillon(parametre: str, nb_observations_resolues: int) -> VerdictGardeFou:
    seuil = TAILLE_MIN_RENFORCEE if _est_renforce(parametre) else TAILLE_MIN_STANDARD
    if nb_observations_resolues < seuil:
        return VerdictGardeFou(
            False,
            f"échantillon insuffisant : {nb_observations_resolues} < {seuil} requis pour {parametre!r}",
        )
    return VerdictGardeFou(True, "")


def verifier_amplitude_cycle(
    parametre: str, valeur_actuelle: float, valeur_proposee: float
) -> VerdictGardeFou:
    if valeur_actuelle == 0:
        return VerdictGardeFou(False, "valeur_actuelle nulle -- amplitude relative indéfinie")
    amplitude = abs(valeur_proposee - valeur_actuelle) / abs(valeur_actuelle)
    plafond = AMPLITUDE_MAX_RENFORCEE if _est_renforce(parametre) else AMPLITUDE_MAX_STANDARD
    if amplitude > plafond:
        return VerdictGardeFou(
            False,
            f"amplitude {amplitude:.1%} > plafond {plafond:.1%} par cycle pour {parametre!r}",
        )
    return VerdictGardeFou(True, "")


def verifier_derive_cumulative(
    parametre: str, valeur_origine: float, valeur_proposee: float
) -> VerdictGardeFou:
    if valeur_origine == 0:
        return VerdictGardeFou(False, "valeur_origine nulle -- dérive relative indéfinie")
    derive = abs(valeur_proposee - valeur_origine) / abs(valeur_origine)
    plafond = DERIVE_MAX_RENFORCEE if _est_renforce(parametre) else DERIVE_MAX_STANDARD
    if derive > plafond:
        return VerdictGardeFou(
            False,
            f"dérive cumulée {derive:.1%} > plafond {plafond:.1%} par rapport à "
            f"l'origine pour {parametre!r}",
        )
    return VerdictGardeFou(True, "")


def verifier_rollback(roi_avant: float, roi_apres: float) -> VerdictGardeFou:
    """autorise=True : la configuration en place reste acceptable, pas de
    retour arrière nécessaire. autorise=False : le ROI s'est dégradé au-delà
    du seuil, un rollback est requis."""
    degradation = roi_avant - roi_apres
    if degradation > SEUIL_ROLLBACK_DEGRADATION:
        return VerdictGardeFou(
            False,
            f"dégradation de ROI {degradation:.1%} > seuil de rollback "
            f"{SEUIL_ROLLBACK_DEGRADATION:.1%}",
        )
    return VerdictGardeFou(True, "")


def autoriser_promotion(
    parametre: str,
    nb_observations_resolues: int,
    valeur_origine: float,
    valeur_actuelle: float,
    valeur_proposee: float,
) -> VerdictGardeFou:
    """Point de passage OBLIGATOIRE avant toute promotion -- calibration.py
    ne doit jamais écrire une nouvelle valeur sans appeler cette fonction et
    vérifier `autorise`. Retourne le PREMIER motif de refus rencontré, dans
    l'ordre : paramètre autorisé -> taille d'échantillon -> amplitude par
    cycle -> dérive cumulée. Un motif antérieur bloque toujours avant qu'un
    motif postérieur ne soit même évalué."""
    verdict = verifier_parametre_autorise(parametre)
    if not verdict.autorise:
        return verdict

    verdict = verifier_taille_echantillon(parametre, nb_observations_resolues)
    if not verdict.autorise:
        return verdict

    verdict = verifier_amplitude_cycle(parametre, valeur_actuelle, valeur_proposee)
    if not verdict.autorise:
        return verdict

    verdict = verifier_derive_cumulative(parametre, valeur_origine, valeur_proposee)
    if not verdict.autorise:
        return verdict

    return VerdictGardeFou(True, "")
