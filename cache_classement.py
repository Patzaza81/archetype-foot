"""
cache_classement.py -- mémoire persistante du classement, par compétition.

AJOUT 03/09/2026, version 2 -- Patrick a directement demandé la vraie
optimisation : tous les matchs d'une même ligue, dans la MÊME fenêtre,
doivent partager un seul classement au lieu que chaque match aille le
re-scraper séparément. La version 1 de ce fichier ne le faisait pas (clé =
URL du match, limite documentée à l'époque) -- corrigé ici en modifiant
aussi le point d'appel dans run_pipeline.py pour qu'il transmette le nom
de la compétition (`recupere_classement_du_match(url_match, competition)`
au lieu de `(url_match)` seul). scraper_details.py accepte ce 2e argument
mais l'ignore -- il ne sert qu'à la clé de cache ici.

Clé : le nom de la compétition (normalisé) -- peu importe QUEL match de la
Ligue 1 déclenche le premier appel, tous les suivants de la même
compétition retombent sur la même entrée.

TTL 12h : un classement change dès qu'un match de la compétition se
termine ; assez long pour survivre à un 2e run le même jour, assez court
pour se rafraîchir avant le lendemain.

N'importe quel appelant doit passer une fonction de calcul (le "vrai"
recupere_classement_du_match) -- ce module ne fait que la mémoire, pas le
scraping lui-même.
"""
import datetime
import json
import os

FICHIER_CACHE = "cache_classement.json"
TTL_HEURES = 12


def _cle(nom_competition):
    return " ".join((nom_competition or "").split()).lower()


def _charge(fichier_cache):
    if not os.path.exists(fichier_cache):
        return {}
    try:
        with open(fichier_cache, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _sauve(cache, fichier_cache):
    with open(fichier_cache, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _expire(entree):
    horodatage = datetime.datetime.fromisoformat(entree["horodatage"])
    age = datetime.datetime.now(datetime.timezone.utc) - horodatage
    return age > datetime.timedelta(hours=TTL_HEURES)


def recupere_classement_avec_cache(fonction_reelle, url_match, nom_competition,
                                    fichier_cache=FICHIER_CACHE):
    """Retourne le classement en cache s'il est encore valide pour cette
    COMPÉTITION (moins de TTL_HEURES), sinon appelle fonction_reelle
    (recupere_classement_du_match) sur CE match précis et mémorise le
    résultat pour tous les autres matchs de la même compétition.

    Si fonction_reelle lève une exception (page introuvable, tableau
    absent...), elle n'est PAS mise en cache -- le prochain match de cette
    compétition retentera le scraping complet, exactement comme pour
    cache_equipes.py."""
    cache = _charge(fichier_cache)
    cle = _cle(nom_competition)

    entree = cache.get(cle)
    if entree and not _expire(entree):
        return entree["resultat"]

    resultat = fonction_reelle(url_match, nom_competition)

    cache[cle] = {
        "horodatage": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "resultat": resultat,
    }
    _sauve(cache, fichier_cache)
    return resultat


def purge_entrees_expirees(fichier_cache=FICHIER_CACHE):
    """À lancer périodiquement, comme pour cache_equipes.py."""
    cache = _charge(fichier_cache)
    encore_valides = {cle: entree for cle, entree in cache.items() if not _expire(entree)}
    if len(encore_valides) != len(cache):
        _sauve(encore_valides, fichier_cache)
    return len(cache) - len(encore_valides)
