"""
archetype_model/h2h/h2h_stats.py — Paliers de fiabilité H2H (v3 §10,
verrouillé) :

    N < 5   -> INSUFFISANT
    5-7     -> INDICATIF
    8-9     -> FIABLE
    >= 10   -> TRÈS FIABLE (plafond : 10 confrontations les plus récentes)

Réutilise `scraper_details.recupere_h2h` en LECTURE SEULE (déjà en
production, déjà testé ailleurs) -- rien n'est modifié.

ORDRE DE PAGE, vérifié le 08/09/2026 sur capture d'écran réelle
(tableau "Confrontations entre les deux équipes") : DÉCROISSANT, plus
récent en premier. C'est l'INVERSE de la convention de
`data.loader` (historique par compétition, lui croissant) -- ce sont
deux tableaux différents de matchendirect.fr, avec des ordres opposés
confirmés séparément. Les 10 plus récents ici = les 10 PREMIERS
éléments de la liste, PAS les 10 derniers -- ne jamais copier la règle
de troncature de `data.validation.classifie_fenetre` (qui fait
l'inverse, `[-12:]`) sur ce module.
"""

from scraper_details import recupere_h2h, _memes_equipes

MAX_CONFRONTATIONS = 10

PALIER_INSUFFISANT = "INSUFFISANT"
PALIER_INDICATIF = "INDICATIF"
PALIER_FIABLE = "FIABLE"
PALIER_TRES_FIABLE = "TRES_FIABLE"


def _normalise_confrontation(confrontation, nom_equipe_a):
    """Une confrontation brute (format `recupere_h2h`) contient
    domicile_brut/exterieur_brut tels qu'ils étaient DANS CETTE
    RENCONTRE PASSÉE PRÉCISE -- l'équipe A n'a pas forcément joué à
    domicile à chaque confrontation. Retourne {"buts_a", "buts_b"} du
    point de vue de A, peu importe son statut domicile/extérieur ce
    jour-là. None si ni domicile_brut ni exterieur_brut ne correspond
    à A (ne devrait jamais arriver sur un vrai H2H, gardé défensif)."""
    if _memes_equipes(nom_equipe_a, confrontation["domicile_brut"]):
        return {"buts_a": confrontation["buts_domicile"], "buts_b": confrontation["buts_exterieur"]}
    if _memes_equipes(nom_equipe_a, confrontation["exterieur_brut"]):
        return {"buts_a": confrontation["buts_exterieur"], "buts_b": confrontation["buts_domicile"]}
    return None


def recupere_confrontations(url_match_face_a_face, nom_equipe_a):
    """
    Récupère le H2H réel (un seul fetch réseau, via
    `scraper_details.recupere_h2h`) et normalise chaque confrontation
    du point de vue de l'équipe A. Les entrées qui ne correspondent à
    aucun des deux noms de `recupere_h2h` sont écartées (défensif,
    jamais une exception).
    """
    confrontations_brutes = recupere_h2h(url_match_face_a_face)
    normalisees = []
    for c in confrontations_brutes:
        n = _normalise_confrontation(c, nom_equipe_a)
        if n is not None:
            normalisees.append(n)
    return normalisees


def classifie_h2h(confrontations_normalisees):
    """
    Retourne {"palier": ..., "n_brut": int, "n_retenu": int,
    "confrontations_retenues": [...]}.

    "confrontations_retenues" = les `MAX_CONFRONTATIONS` (10) PREMIERS
    éléments de la liste reçue (déjà décroissante, voir docstring de
    module) -- jamais plus, même si `n_brut` est supérieur.
    """
    n_brut = len(confrontations_normalisees)
    confrontations_retenues = confrontations_normalisees[:MAX_CONFRONTATIONS]
    n_retenu = len(confrontations_retenues)

    if n_retenu < 5:
        palier = PALIER_INSUFFISANT
    elif n_retenu <= 7:
        palier = PALIER_INDICATIF
    elif n_retenu <= 9:
        palier = PALIER_FIABLE
    else:
        palier = PALIER_TRES_FIABLE

    return {
        "palier": palier,
        "n_brut": n_brut,
        "n_retenu": n_retenu,
        "confrontations_retenues": confrontations_retenues,
    }
