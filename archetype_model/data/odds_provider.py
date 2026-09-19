"""
archetype_model/data/odds_provider.py — Adaptateur de cotes réelles.

Lecture seule : ne scrape rien, ne calcule ni Edge ni EDV, ne sélectionne
rien. Traduit le format déjà produit par le pipeline vers les clés internes
d'archetype_model.

RÈGLE DE SÉCURITÉ : un marché dont la correspondance cote -> calcul n'est
pas démontrée est refusé, jamais approximé.
"""

import json
import re

_LIBELLES_STATIQUES = {
    "1X2 - 1": ("1x2", "domicile"),
    "1X2 - X": ("1x2", "nul"),
    "1X2 - 2": ("1x2", "exterieur"),
    "Double chance - 1X": ("double_chance", "1X"),
    "Double chance - X2": ("double_chance", "X2"),
    "Double chance - 12": ("double_chance", "12"),
    "BTTS - oui": ("btts", "oui"),
    "BTTS - non": ("btts", "non"),
    "Cage inviolée - Domicile": ("buts_equipe_exterieur", 0.5, "under"),
    "Encaisse au moins 1 but - Domicile": ("buts_equipe_exterieur", 0.5, "over"),
    "Cage inviolée - Extérieur": ("buts_equipe_domicile", 0.5, "under"),
    "Encaisse au moins 1 but - Extérieur": ("buts_equipe_domicile", 0.5, "over"),
}

_RE_BUTS = re.compile(r"^(Plus|Moins) de (\d+(?:\.\d+)?) buts(?: - (Domicile|Extérieur))?$")
# Périmètre volontairement limité au marché Betpawa : « Handicap À 3 Choix | Fin de Match ».
# Les trois issues d'une même ligne partagent une seule ligne interne normalisée.
_RE_HANDICAP_3 = re.compile(r"^(Domicile|Nul|Extérieur)\s+([+-]?\d+)$", re.IGNORECASE)


def _parse_libelle(libelle):
    if libelle in _LIBELLES_STATIQUES:
        return _LIBELLES_STATIQUES[libelle]