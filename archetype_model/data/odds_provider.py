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
    "Total buts - pair": ("parite_totale", "pair"),
    "Total buts - impair": ("parite_totale", "impair"),
    "Cage inviolée - Domicile": ("buts_equipe_exterieur", 0.5, "under"),
    "Encaisse au moins 1 but - Domicile": ("buts_equipe_exterieur", 0.5, "over"),
    "Cage inviolée - Extérieur": ("buts_equipe_domicile", 0.5, "under"),
    "Encaisse au moins 1 but - Extérieur": ("buts_equipe_domicile", 0.5, "over"),
}

_RE_BUTS = re.compile(r"^(Plus|Moins) de (\d+(?:\.\d+)?) buts(?: - (Domicile|Extérieur))?$")
# Périmètre volontairement limité au marché Betpawa : « Handicap À 3 Choix | Fin de Match ».
# La clé interne stocke toujours la ligne appliquée au domicile.
_RE_HANDICAP_3 = re.compile(r"^(Domicile|Nul|Extérieur)\s+([+-]?\d+)$", re.IGNORECASE)
_RE_COMBO = re.compile(
    r"^(?:Double chance\s*-\s*)?(1X|X2|12)\s*\+\s*(Plus|Moins) de (\d+(?:\.\d+)?) buts$",
    re.IGNORECASE,
)


def _parse_libelle(libelle):
    if libelle in _LIBELLES_STATIQUES:
        return _LIBELLES_STATIQUES[libelle]
    m = _RE_COMBO.match(libelle or "")
    if m:
        dc, sens_fr, ligne_str = m.groups()
        sens = "over" if sens_fr.lower() == "plus" else "under"
        return ("combo_dc_total", dc.upper(), sens, float(ligne_str))
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
        ligne = float(ligne_str)
        sel = sel.lower()
        if sel == "domicile":
            ligne_domicile = ligne
            selection = "domicile"
        elif sel == "nul":
            ligne_domicile = ligne
            selection = "nul"
        else:
            # Betpawa affiche le handicap du côté extérieur avec le signe
            # opposé. On normalise vers la ligne appliquée au domicile afin
            # que les trois issues d'une même ligne utilisent exactement
            # la même référence mathématique.
            ligne_domicile = -ligne
            selection = "exterieur"
        return ("handicap_3choix", ligne_domicile, selection)
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
