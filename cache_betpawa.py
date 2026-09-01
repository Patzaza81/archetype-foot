"""
cache_betpawa.py -- Mémoire persistante des correspondances Betpawa
CERTAINES (jamais des AMBIGU ni des NON TROUVÉ), avec traçabilité
complète. Vient en complément de resolution_betpawa.py, sans jamais en
modifier la logique.

Un match donné (mêmes équipes, même date) reste dans la fenêtre active
J+1/J+2/J+3 pendant jusqu'à 3 nuits avant d'être joué -- ce cache évite
de refaire toute la recherche Betpawa (recherche + comparaison + 
vérification de date) à chaque nuit pour un match déjà résolu la veille.

Clé de cache : (nom_domicile, nom_exterieur, date_iso) tels que fournis
par matchendirect -- normalisés pour éviter les doublons dus à la
casse/espaces, mais SANS tenter de généraliser au-delà de ce match
précis (pas un référentiel d'alias d'équipes -- volontairement laissé
pour plus tard, "si nécessaire", comme demandé).
"""
import datetime
import json
import os

from resolution_betpawa import normalise

FICHIER_CACHE = "cache_betpawa.json"


def _cle(nom_domicile, nom_exterieur, date_iso):
    dom = " ".join(normalise(nom_domicile))
    ext = " ".join(normalise(nom_exterieur))
    return f"{dom}||{ext}||{date_iso}"


def _charge(fichier_cache=FICHIER_CACHE):
    if not os.path.exists(fichier_cache):
        return {}
    try:
        with open(fichier_cache, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _sauve(cache, fichier_cache=FICHIER_CACHE):
    with open(fichier_cache, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def cherche_dans_cache(nom_domicile, nom_exterieur, date_iso, fichier_cache=FICHIER_CACHE):
    """Retourne l'enregistrement complet si une correspondance CERTAINE
    est déjà connue pour ce match précis, sinon None. Ne renvoie jamais
    un AMBIGU ou un NON TROUVÉ -- ces cas-là ne sont jamais persistés
    (voir enregistre_correspondance)."""
    cache = _charge(fichier_cache)
    cle = _cle(nom_domicile, nom_exterieur, date_iso)
    return cache.get(cle)


def enregistre_correspondance(nom_domicile, nom_exterieur, date_iso, event_id_url,
                               home_betpawa=None, away_betpawa=None, competition=None,
                               tamis="inconnu", fichier_cache=FICHIER_CACHE):
    """N'enregistre QUE des correspondances certaines (confidence
    "certain") -- jamais appelé pour un AMBIGU ou un NON TROUVÉ. C'est à
    l'appelant de ne PAS invoquer cette fonction dans ces deux cas."""
    cache = _charge(fichier_cache)
    cle = _cle(nom_domicile, nom_exterieur, date_iso)
    cache[cle] = {
        "match_key": cle,
        "home_source": nom_domicile,
        "away_source": nom_exterieur,
        "home_betpawa": home_betpawa,
        "away_betpawa": away_betpawa,
        "event_id": event_id_url,
        "date": date_iso,
        "competition": competition,
        "confidence": "certain",
        "verified_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": f"resolution_betpawa ({tamis})",
    }
    _sauve(cache, fichier_cache)


def purge_matchs_joues(dates_encore_actives, fichier_cache=FICHIER_CACHE):
    """À lancer périodiquement (pas à chaque run) pour ne pas laisser le
    cache grossir indéfiniment avec des matchs déjà joués depuis
    longtemps. dates_encore_actives : ensemble de dates ISO encore
    utiles (ex. J+1/J+2/J+3 actuels) -- tout le reste peut être purgé.
    L'historique des matchs joués n'a pas besoin de rester dans CE
    cache (qui sert à accélérer les recherches actives), contrairement
    à historique_pronostics.json qui, lui, garde tout pour la
    calibration."""
    cache = _charge(fichier_cache)
    encore_utiles = {cle: v for cle, v in cache.items() if v.get("date") in dates_encore_actives}
    if len(encore_utiles) != len(cache):
        _sauve(encore_utiles, fichier_cache)
    return len(cache) - len(encore_utiles)
