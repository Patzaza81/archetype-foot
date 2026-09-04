"""
cache_h2h.py -- mémoire persistante de l'historique des confrontations
directes (face-à-face), pour ne pas le re-scraper si le pipeline est
relancé sur les mêmes matchs.

AJOUT 03/09/2026 -- même demande de Patrick que cache_classement.py : un
2e run le même jour (ou un match qui reste dans la fenêtre plusieurs
nuits de suite, ex. J+3 qui devient J+2 puis J+1) ne doit pas re-scraper
un historique de confrontations qui n'a aucune raison d'avoir changé.

LIMITE CONNUE (assumée, la même que cache_classement.py) : la clé de
cache est l'URL du match, pas les deux noms d'équipes. recupere_h2h(url,
max_confrontations) ne reçoit que l'URL -- ajouter les noms d'équipes à sa
signature toucherait l'appel dans run_pipeline.py, utilisé aussi par le
flux panier manuel. Conséquence : un run relancé sur le même match
réutilise bien le H2H (le but demandé) ; ça ne fusionne pas un éventuel
aller/retour (deux URLs différentes, mêmes équipes) -- cas rare, non
demandé ici.

TTL long (7 jours) : contrairement au classement, l'historique de
confrontations entre deux équipes précises ne change que si elles se
rejouent -- un événement rare à l'échelle de quelques jours.

N'importe quel appelant doit passer une fonction de calcul (le "vrai"
recupere_h2h) -- ce module ne fait que la mémoire, pas le scraping
lui-même. Ainsi scraper_details.py et run_pipeline.py restent inchangés.
"""
import datetime
import json
import os

FICHIER_CACHE = "cache_h2h.json"
TTL_HEURES = 24 * 7


def _cle(url_match_face_a_face):
    return (url_match_face_a_face or "").strip().lower()


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


def recupere_h2h_avec_cache(fonction_reelle, url_match_face_a_face,
                             max_confrontations=20, fichier_cache=FICHIER_CACHE):
    """Retourne le H2H en cache s'il est encore valide pour ce match, sinon
    appelle fonction_reelle (recupere_h2h) et mémorise le résultat. Échec
    (exception) : pas mis en cache, comme cache_equipes.py."""
    cache = _charge(fichier_cache)
    cle = _cle(url_match_face_a_face)

    entree = cache.get(cle)
    if entree and not _expire(entree):
        return entree["resultat"]

    resultat = fonction_reelle(url_match_face_a_face, max_confrontations)

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
