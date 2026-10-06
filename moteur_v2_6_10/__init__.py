# -*- coding: utf-8 -*-
"""moteur_v2_6_10 : moteur autonome (noyau hérité de la v2.6.9) + lissage par rôle + calibration optionnelle cohérente + alertes
(ossature P1/P2/P3 inchangée)."""
from . import noyau
from .calibration import CalibrateurIsotone, apprendre, avant, dedoublonne
from .coherence import harmonise
from .core import NOM_MOTEUR, VERSION_MOTEUR, analyser_match, signature_modele
from .lissage import K_LISSAGE, PARAMETRES_PAR_DEFAUT, REF_BUTS_DOM, REF_BUTS_EXT, ParametresLissage, lisse, lisser_match

__all__ = ["analyser_match", "signature_modele", "NOM_MOTEUR", "VERSION_MOTEUR", "CalibrateurIsotone", "apprendre", "avant",
           "dedoublonne", "harmonise", "lisse", "lisser_match", "ParametresLissage", "PARAMETRES_PAR_DEFAUT", "K_LISSAGE",
           "REF_BUTS_DOM", "REF_BUTS_EXT", "noyau"]
