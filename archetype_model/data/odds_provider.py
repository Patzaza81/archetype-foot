"""
archetype_model/data/odds_provider.py — Adaptateur de cotes réelles,
LECTURE SEULE. Ne scrape rien, ne calcule ni Edge ni EDV, ne sélectionne
rien. Traduit uniquement le format déjà produit par le pipeline
existant vers les clés internes d'archetype_model.

SOURCE CHOISIE (audit du 08/09/2026, pas une supposition) :
`precalcul.json` → `signaux[].TOUS_MARCHES_EVALUES` -- liste plate
{"marche": "<libellé français>", "cote_observee": <float>,
"probabilite_modele": <float>} présente pour TOUS les matchs traités
(READY et PARTIAL), quelle que soit l'origine réelle de la cote
(`source_cotes` vaut soit "matchendirect_bet365" soit "manuel").

Le champ `probabilite_modele` de ces entrées est la probabilité de
L'ANCIEN MOTEUR -- JAMAIS lu ni réutilisé ici, même par accident.
Seul `cote_observee` est extrait.

RAPPEL DE PATRICK (08/09/2026), à ne pas oublier pour la suite mais qui
NE bloque PAS ce module : Betpawa est le site où le pari s'exécute
réellement, à privilégier dès qu'un arbitrage entre plusieurs sources
sera nécessaire. Aujourd'hui, `source_cotes == "manuel"` est le seul
indicateur disponible dans precalcul.json pour repérer les cotes
Betpawa (vs "matchendirect_bet365") -- exposé ici via `est_betpawa`
pour rendre ce futur arbitrage possible sans reprendre la plomberie,
mais aucune préférence n'est appliquée pour l'instant : une seule
source de cote par match existe dans precalcul.json aujourd'hui, pas
un choix entre plusieurs.

MARCHÉS NON COUVERTS, assumé et documenté (pas une erreur silencieuse) :
`precalcul.json` fournit des cotes pour "Cage inviolée" (clean sheet)
et "Total buts - pair/impair" (v3 §9.2 : familles CLEAN_SHEET et
PAIR_IMPAIR) -- non codées dans poisson/markets.py à ce jour. Ces
libellés sont reconnus comme "non couverts", jamais silencieusement
ignorés : voir `marches_non_couverts` dans le résultat.
"""

import json
import re

# --- Traduction libellé français -> clé structurée archetype_model ---

_LIBELLES_STATIQUES = {
    "1X2 - 1": ("1x2", "domicile"),
    "1X2 - X": ("1x2", "nul"),
    "1X2 - 2": ("1x2", "exterieur"),
    "Double chance - 1X": ("double_chance", "1X"),
    "Double chance - X2": ("double_chance", "X2"),
    "Double chance - 12": ("double_chance", "12"),
    "BTTS - oui": ("btts", "oui"),
    "BTTS - non": ("btts", "non"),
}

_RE_BUTS = re.compile(r"^(Plus|Moins) de (\d+(?:\.\d+)?) buts(?: - (Domicile|Extérieur))?$")
_RE_HANDICAP = re.compile(r"^Handicap (-?\d+(?:\.\d+)?) - (Domicile|Extérieur)$")


def _parse_libelle(libelle):
    """
    Traduit un libellé français de precalcul.json en clé structurée
    reconnue par archetype_model : (famille, ligne, sens) pour les
    marchés paramétrés (total, buts par équipe, handicap), (famille,
    selection) pour les marchés fixes (1X2, DC, BTTS).

    Retourne None si le libellé n'est PAS (encore) couvert par
    archetype_model (ex. "Cage inviolée - Domicile") -- ce n'est pas
    une erreur de format, juste un marché non codé côté archetype_model
    à ce jour (voir docstring du module).
    """
    if libelle in _LIBELLES_STATIQUES:
        return _LIBELLES_STATIQUES[libelle]

    m = _RE_BUTS.match(libelle)
    if m:
        sens_fr, ligne_str, cote_partie = m.groups()
        ligne = float(ligne_str)
        sens = "over" if sens_fr == "Plus" else "under"
        if cote_partie is None:
            return ("over_under_total", ligne, sens)
        elif cote_partie == "Domicile":
            return ("buts_equipe_domicile", ligne, sens)
        else:
            return ("buts_equipe_exterieur", ligne, sens)

    m = _RE_HANDICAP.match(libelle)
    if m:
        ligne_str, cote_partie = m.groups()
        ligne = float(ligne_str)
        cote_selection = "domicile" if cote_partie == "Domicile" else "exterieur"
        return ("handicap", ligne, cote_selection)

    return None


def extrait_cotes(signal_match):
    """
    `signal_match` : une entrée de `precalcul.json["signaux"]` déjà
    chargée en mémoire (pas de lecture fichier ici).

    Retourne {"cotes": {clé_structurée: cote_decimale}, "source_cotes":
    str|None, "est_betpawa": bool, "marches_non_couverts": [libellés]}.

    Une entrée `TOUS_MARCHES_EVALUES` sans `cote_observee` exploitable
    (absente, None, ou pas un nombre) est ignorée silencieusement pour
    CETTE entrée précise, sans faire échouer l'extraction des autres
    marchés du même match -- un problème sur une ligne ne doit jamais
    priver le reste du match de ses cotes valides.
    """
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
    """
    Point d'entrée principal. Cherche `match_id` dans
    `precalcul.json["signaux"]` et retourne le résultat d'`extrait_cotes`,
    enrichi d'un statut explicite.

    Retourne {"statut": "OK"|"MATCH_INTROUVABLE", "cotes": {...},
    "source_cotes": ..., "est_betpawa": ..., "marches_non_couverts": [...]}.
    "MATCH_INTROUVABLE" -> "cotes" vide, jamais une exception : le
    match n'a peut-être pas encore été traité par le pipeline existant,
    ce n'est pas une erreur de ce module.
    """
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
