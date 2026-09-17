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
- une équipe SANS historique connu (raison_non_traite) : cache moyen
  (TTL_SANS_HISTORIQUE_HEURES) -- réduit de 7 jours à 4 jours (décision de
  Patrick, 06/09/2026, point #30 de l'audit) : un cache de 7 jours pouvait
  masquer une récupération devenue possible entre-temps (ex. une équipe
  qui n'avait simplement pas encore joué cette saison au moment du
  premier scraping).
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
# CORRECTIF 06/09/2026 (bug #30, décision de Patrick) -- 7 jours (24*7)
# réduit à 4 jours (24*4).
TTL_SANS_HISTORIQUE_HEURES = 24 * 4   # un club amateur en coupe prélim.
                                        # ne va pas soudain avoir un
                                        # historique le lendemain -- mais
                                        # 4 jours plutôt que 7 pour ne pas
                                        # masquer trop longtemps une
                                        # équipe qui vient de jouer son
                                        # premier match de la saison
# CORRECTIF 17/09/2026 (Patrick, run du 16-17/09 -- durée totale 4h35,
# dont ~2h44 de scraping matchendirect.fr par équipe alors que la
# quasi-totalité des équipes avaient déjà un cache_equipes.json valide
# de la veille). Cause : TTL de 20h < intervalle réel entre deux runs
# planifiés (~24h, cron 21:00 UTC quotidien, parfois retardé -- un run
# a démarré avec 2h28 de retard, voir commentaire pipeline.yml
# 12/09/2026). Un TTL plus court que l'intervalle entre runs garantit
# que CHAQUE équipe est "expirée" à CHAQUE run, ce qui annule le
# bénéfice du cache pour la quasi-totalité des matchs traités chaque
# nuit (l'intention initiale du 06/09/2026 -- "moins d'une journée pour
# laisser le temps à un nouveau résultat de rentrer avant le prochain
# run" -- se retourne contre elle-même : elle force un re-scraping
# systématique au lieu d'un rafraîchissement ciblé sur les équipes qui
# ont réellement rejoué depuis le dernier cache).
#
# 30h choisi pour couvrir l'intervalle réel avec marge (24h + retard
# cron plausible), tout en restant strictement < 96h (TTL_SANS_HISTORIQUE)
# et < 1 semaine -- une équipe qui joue son prochain match dans les 30h
# suivant le dernier scraping aura une donnée vieille d'un run (jamais
# plus), ce qui reste dans l'esprit "à jour avant le prochain run"
# d'origine, sans annuler le cache chaque nuit.
TTL_AVEC_HISTORIQUE_HEURES = 30        # couvre l'intervalle réel entre
                                        # deux runs planifiés (~24h +
                                        # marge de retard cron), pour
                                        # que le cache serve réellement
                                        # au lieu d'expirer chaque nuit


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
