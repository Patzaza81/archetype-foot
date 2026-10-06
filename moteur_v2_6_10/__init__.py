# -*- coding: utf-8 -*-
"""moteur_v2_6_10 : moteur_v2_6_9 + lissage par rôle + calibration optionnelle cohérente + alertes (ossature P1/P2/P3 inchangée)."""
from .calibration import CalibrateurIsotone, apprendre, avant, dedoublonne
from .coherence import harmonise
from .core import NOM_MOTEUR, VERSION_MOTEUR, analyser_match, signature_modele
from .lissage import K_LISSAGE, PARAMETRES_PAR_DEFAUT, REF_BUTS_DOM, REF_BUTS_EXT, ParametresLissage, lisse, lisser_match



# Compatibilité : le pont et les tests historiques utilisent encore certains symboles publics de la v2.6.9\n# (charger_matchs, MARCHES_STANDARD, LIGNES_HANDICAP, etc.). Ils restent disponibles comme dépendances internes.\ndef __getattr__(name):\n    import moteur_v2_6_9 as _base\n    return getattr(_base, name)\n\n__all__ = ["analyser_match", "signature_modele", "NOM_MOTEUR", "VERSION_MOTEUR", "CalibrateurIsotone", "apprendre", "avant",
           "dedoublonne", "harmonise", "lisse", "lisser_match", "ParametresLissage", "PARAMETRES_PAR_DEFAUT", "K_LISSAGE",
           "REF_BUTS_DOM", "REF_BUTS_EXT"]
