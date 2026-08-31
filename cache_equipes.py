"""
cache_equipes.py -- mémoire persistante de ce qu'on sait déjà sur chaque
équipe (dans une compétition donnée), pour ne pas refaire les mêmes
requêtes réseau chaque nuit.

Pourquoi la clé est (url_equipe, compétition) et pas juste url_equipe :
recupere_gf_ga_avec_repli() filtre l'historique par compétition (une
même équipe a un historique différent selon le tournoi, cf.
_extrait_historique_competition dans scraper_details.py) -- un cache par
équipe seule mélangerait les deux et donnerait un mauvais résultat.

Deux durées de validité différentes, volontairement :
- une équipe SANS historique connu (raison_non_traite) : ça ne va pas
  changer d'un jour à l'autre pour un petit club en coupe préliminaire.
  Cache long (TTL_SANS_HISTORIQUE_HEURES).
- une équipe avec des stats réelles : ses derniers résultats peuvent
  changer si elle joue entre-temps. Cache plus court
  (TTL_AVEC_HISTORIQUE_HEURES).

N'importe quel appelant doit passer une fonction de calcul (le "vrai"
recupere_gf_ga_avec_repli) -- ce module ne fait que la mémoire, pas le
scraping lui-même. Ainsi scraper_details.py et run_pipeline.py restent
inchangés.
"""
import datetime
import json
import os

FICHIER_CACHE = "cache_equipes.json"
TTL_SANS_HISTORIQUE_HEURES = 24 * 7   # un club amateur en coupe prélim.
                                        # ne va pas soudain avoir un
                                        # historique le lendemain
TTL_AVEC_HISTORIQUE_HEURES = 20        # un peu moins d'une journée --
                                        # laisse le temps à un nouveau
                                        # résultat de rentrer avant le
                                        # prochain run planifié


def _cle(url_equipe, nom_competition):
    # même normalisation basique que le reste du projet : espaces multiples
    # réduits, insensible à la casse, pour éviter deux entrées pour la même
    # paire à cause d'un espace ou d'une majuscule différente
    comp = " ".join((nom_competition or "").split()).lower()
    return f"{url_equipe}||{comp}"


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
    ttl_heures = (
        TTL_SANS_HISTORIQUE_HEURES
        if "raison_non_traite" in entree["resultat"]
        else TTL_AVEC_HISTORIQUE_HEURES
    )
    age = datetime.datetime.now(datetime.timezone.utc) - horodatage
    return age > datetime.timedelta(hours=ttl_heures)


def recupere_gf_ga_avec_cache(fonction_reelle, url_equipe, nom_equipe,
                               nom_competition, max_matchs,
                               fichier_cache=FICHIER_CACHE):
    """Retourne le résultat en cache s'il est encore valide, sinon appelle
    fonction_reelle (recupere_gf_ga_avec_repli) et mémorise le résultat."""
    cache = _charge(fichier_cache)
    cle = _cle(url_equipe, nom_competition)

    entree = cache.get(cle)
    if entree and not _expire(entree):
        return entree["resultat"]

    resultat = fonction_reelle(url_equipe, nom_equipe, nom_competition, max_matchs=max_matchs)

    cache[cle] = {
        "horodatage": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "resultat": resultat,
    }
    _sauve(cache, fichier_cache)
    return resultat


def purge_entrees_expirees(fichier_cache=FICHIER_CACHE):
    """À lancer périodiquement (ex. une fois par semaine dans le workflow)
    pour ne pas laisser le fichier grossir indéfiniment avec des équipes
    qui ne reviennent plus dans la fenêtre J+1/J+2/J+3."""
    cache = _charge(fichier_cache)
    encore_valides = {cle: entree for cle, entree in cache.items() if not _expire(entree)}
    if len(encore_valides) != len(cache):
        _sauve(encore_valides, fichier_cache)
    return len(cache) - len(encore_valides)
