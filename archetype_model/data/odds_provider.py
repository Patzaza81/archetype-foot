"""
archetype_model/data/odds_provider.py — Adaptateur de cotes réelles.

Lecture seule : ne scrape rien, ne calcule ni Edge ni EDV, ne sélectionne
rien. Traduit le format déjà produit par le pipeline vers les clés internes
d'archetype_model.

RÈGLE DE SÉCURITÉ : un marché dont la correspondance cote -> calcul n'est
pas démontrée est refusé, jamais approximé.

CORRECTIF 19/09/2026 -- ce fichier était tombé de 113 à 37 lignes après le
commit "Sélection marchés : supprimer parsing parité et combos" (09212d7) :
la suppression, censée ne retirer que la parité (pair/impair) et les
combos (double chance + total), a aussi effacé par erreur le handicap
3 choix, le parsing over/under simple, ET extrait_cotes()/
recupere_cotes_pour_match() -- deux fonctions sans aucun rapport avec
parité ou combos, utilisées par tout le reste du pipeline pour lire les
cotes. Reconstruit à l'identique depuis le dernier commit sain (2ed4db2),
en ne retirant que ce qui était réellement visé : les entrées statiques
"Total buts - pair/impair" (parité) et _RE_COMBO + sa branche (combos).
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
    m = _RE_BUTS.match(libelle or "")
    if m:
        sens_fr, ligne_str, cote_partie = m.groups()
        ligne = float(ligne_str)
        sens = "over" if sens_fr == "Plus" else "under"
        if cote_partie is None:
            return ("over_under_total", ligne, sens)
        if cote_partie == "Domicile":
            return ("buts_equipe_domicile", ligne, sens)
        return ("buts_equipe_exterieur", ligne, sens)
    m = _RE_HANDICAP_3.match(libelle or "")
    if m:
        sel, ligne_str = m.groups()
        # Le moteur principal reçoit une ligne interne positive puis applique
        # -ligne à resultat_handicap(), qui représente le handicap domicile.
        # Ainsi Domicile -3, Nul -3 et Extérieur +3 utilisent exactement
        # la même référence mathématique : h = -3.
        ligne_interne = abs(float(ligne_str))
        sel = sel.lower()
        if sel == "domicile":
            return ("handicap_3choix", ligne_interne, "domicile")
        if sel == "nul":
            return ("handicap_3choix", ligne_interne, "nul")
        if sel == "extérieur":
            return ("handicap_3choix", ligne_interne, "exterieur")
    return None


def extrait_cotes(signal_match):
    cotes = {}
    marches_non_couverts = []
    for entree in signal_match.get("TOUS_MARCHES_EVALUES", []):
        libelle = entree.get("marche")
        cote = entree.get("cote_observee")
        if libelle is None or not isinstance(cote, (int, float)):
            continue
        cle = _parse_libelle(libelle)
        if cle is None:
            marches_non_couverts.append(libelle)
        else:
            cotes[cle] = float(cote)
    return {
        "cotes": cotes,
        "source_cotes": signal_match.get("source_cotes"),
        "est_betpawa": signal_match.get("source_cotes") == "manuel",
        "marches_non_couverts": marches_non_couverts,
    }


def recupere_cotes_pour_match(match_id, chemin_precalcul="precalcul.json"):
    with open(chemin_precalcul, "r", encoding="utf-8") as f:
        precalcul = json.load(f)
    for signal_match in precalcul.get("signaux", []):
        if signal_match.get("match_id") == match_id:
            resultat = extrait_cotes(signal_match)
            resultat["statut"] = "OK"
            return resultat
    return {
        "statut": "MATCH_INTROUVABLE",
        "cotes": {},
        "source_cotes": None,
        "est_betpawa": False,
        "marches_non_couverts": [],
    }
