"""
archetype_model/statistics/profil_equipe.py — Profil qualitatif enrichi
d'une équipe pour SON RÔLE dans le match analysé (domicile ou
extérieur), construit UNIQUEMENT à partir de team_stats.py et
goals.py déjà existants et déjà testés -- aucune nouvelle collecte de
données, aucune modification de main.py/selector.py/convergence.py.

RÈGLE DE RÔLE (demande explicite de Patrick, 16/09/2026) : pour une
équipe à domicile dans le match analysé, TOUTES les statistiques de ce
profil viennent de SA fenêtre domicile uniquement (jamais mélangée
avec ses matchs à l'extérieur) ; symétriquement pour l'équipe à
l'extérieur. C'est déjà ce que fait le calcul du lambda dans main.py
(stats_off_a/stats_def_a sur matchs_dom_domicile) -- ce module
généralise ce même principe à un jeu de statistiques plus large, pour
faire apparaître des tendances AVANT tout calcul de lambda/EDV.

TROU DE FIABILITÉ CORRIGÉ ICI (trouvé le 16/09/2026 en auditant le
code sur une question de Patrick) : `data.validation.classifie_fenetre`
n'exige que N_MIN_UTILISABLE=5 matchs TOTAUX (domicile+extérieur
confondus) avant de déclarer une équipe UTILISABLE -- mais le
sous-échantillon réellement utilisé après séparation domicile/
extérieur (`data.loader.separe_domicile_exterieur`) peut ensuite être
beaucoup plus petit (ex. 1 seul match domicile sur 5 matchs totaux)
sans qu'aucun garde-fou ne le signale. `construit_profil` calcule donc
un statut de fiabilité SÉPARÉ, sur le sous-échantillon réel utilisé
ici -- jamais sur le n_brut de la fenêtre globale.

Attend en entrée une liste de matchs DÉJÀ FILTRÉE PAR RÔLE (le
résultat de `data.loader.separe_domicile_exterieur(...)`, côté
domicile pour l'équipe à domicile, côté extérieur pour l'équipe à
l'extérieur) -- ce module ne fait aucun filtrage lui-même, il décrit
la liste reçue telle quelle (même contrat que team_stats.py).
"""

from __future__ import annotations

from typing import Any

from . import team_stats, goals
from .distributions import moyenne, variance, ecart_type

# Seuil de fiabilité du SOUS-ÉCHANTILLON par rôle (domicile seul ou
# extérieur seul), distinct de N_MIN_UTILISABLE=5 de validation.py qui
# porte sur le total domicile+extérieur. Valeur V1, NON CALIBRÉE --
# même statut que ROBUSTNESS_STD_THRESHOLD à l'origine (§ garde_fous.py) :
# un choix de départ raisonnable, jamais présenté comme calibré sur
# données réelles tant qu'il ne l'est pas.
N_MIN_PROFIL_FIABLE = 4

STATUT_FIABLE = "FIABLE"
STATUT_A_SURVEILLER = "A_SURVEILLER"  # sous N_MIN_PROFIL_FIABLE, jamais bloquant, juste signalé

# CORRECTIF 16/09/2026 (demande explicite de Patrick) -- le statut
# binaire ci-dessus ne distingue pas 1 match de 3 : un échantillon de 1
# n'a pas le même risque de "fausse illusion" qu'un échantillon de 3.
# Coefficient GRADUÉ, V1 NON CALIBRÉ (mêmes réserves que ci-dessus) --
# progression délibérément non linéaire : le gain de fiabilité entre 0
# et 1 match est énorme (on passe d'aucune donnée à une seule
# observation bruyante), le gain entre 4 et 5 est marginal (la fenêtre
# est déjà réputée exploitable par validation.py à ce stade). Jamais
# utilisé pour bloquer un calcul (ce n'est pas son rôle, contrairement
# à N_MIN_PROFIL_FIABLE) -- seulement pour PONDÉRER la confiance
# accordée à un signal en aval (matrice_croisement.py).
_TABLE_POIDS_FIABILITE = {0: 0.0, 1: 0.25, 2: 0.45, 3: 0.65, 4: 0.85}
POIDS_FIABILITE_PLEIN = 1.0  # n >= 5


def poids_fiabilite(n: int) -> float:
    """Coefficient de fiabilité gradué entre 0.0 (aucune donnée) et 1.0
    (fenêtre pleinement fiable, n>=5) -- jamais un seuil binaire."""
    return _TABLE_POIDS_FIABILITE.get(n, POIDS_FIABILITE_PLEIN)


def _coefficient_variation(m: float | None, sigma: float | None) -> float | None:
    """Écart-type / moyenne -- mesure de régularité indépendante de
    l'échelle (une équipe à 1.0 but/match +-0.2 est plus régulière
    qu'une équipe à 1.0 +-0.9, même moyenne). None si moyenne nulle ou
    absente (division impossible, jamais une fausse valeur 0)."""
    if m is None or sigma is None or m == 0:
        return None
    return sigma / m


def _frequence_egale(valeurs: list[int], valeur_cible: int) -> float | None:
    """Fréquence des matchs où `valeurs[i] == valeur_cible` exactement
    -- distinct de _frequence_seuil (>=), nécessaire pour "n'a marqué
    aucun but" où un seuil >=0 serait trivialement toujours vrai."""
    if not valeurs:
        return None
    return sum(1 for v in valeurs if v == valeur_cible) / len(valeurs)


def _frequence_seuil(valeurs: list[int], seuil_inclusif: int) -> float | None:
    """Fréquence des matchs où `valeurs[i] >= seuil_inclusif` --
    complète la moyenne par la FORME de la distribution (ex. 40% des
    matchs à 0 but marqué décrit une équipe différente de 40% à
    exactement 1, même si la moyenne peut être identique)."""
    if not valeurs:
        return None
    return sum(1 for v in valeurs if v >= seuil_inclusif) / len(valeurs)


def _forme_ponderee_recence(matchs: list[dict[str, Any]]) -> float | None:
    """Points (victoire=3, nul=1, défaite=0) pondérés par récence --
    poids linéaire croissant du plus ancien (poids 1) au plus récent
    (poids len(matchs)), normalisé en points/match pondéré ENTRE 0 et 3
    pour rester comparable à une moyenne de points brute. Répond au
    principe validation.py (l'ordre reçu est croissant, plus récent en
    dernier) -- ne PAS inverser cette hypothèse ici sans vérifier
    data.loader.ASSUME_ORDRE_CROISSANT d'abord."""
    n = len(matchs)
    if n == 0:
        return None
    poids_total = sum(range(1, n + 1))
    if poids_total == 0:
        return None
    points = 0.0
    for i, m in enumerate(matchs, start=1):
        if m["buts_marques"] > m["buts_encaisses"]:
            pts = 3
        elif m["buts_marques"] == m["buts_encaisses"]:
            pts = 1
        else:
            pts = 0
        points += pts * i
    return points / poids_total


def _serie_actuelle(matchs: list[dict[str, Any]], condition) -> int:
    """Longueur de la série EN COURS (les derniers matchs consécutifs
    qui vérifient `condition`), en partant du plus récent (dernier
    élément, ASSUME_ORDRE_CROISSANT) et en remontant tant que la
    condition tient. S'arrête au premier match qui la brise -- une
    série est par définition ININTERROMPUE, jamais la fréquence totale
    sur toute la fenêtre (ça, c'est déjà freq_clean_sheet etc.)."""
    serie = 0
    for m in reversed(matchs):
        if condition(m):
            serie += 1
        else:
            break
    return serie


def _musique(valeurs: list[int]) -> str:
    """Représentation compacte "1-2-0-6-1" de la séquence, plus ancien
    en premier -- pour affichage/justification humaine uniquement,
    jamais reparsée ailleurs dans le code (les séries ci-dessus sont
    calculées directement sur la liste de matchs, pas sur cette
    chaîne)."""
    return "-".join(str(v) for v in valeurs)


def construit_profil(matchs_role: list[dict[str, Any]]) -> dict[str, Any]:
    """Construit le profil qualitatif complet pour UNE équipe dans SON
    RÔLE (domicile ou extérieur) sur SA fenêtre déjà filtrée par rôle.

    Ne retourne jamais None : un échantillon vide ou trop petit produit
    un profil avec des valeurs None et statut_fiabilite=A_SURVEILLER,
    jamais une exception -- à l'appelant de décider quoi faire d'un
    profil peu fiable (jamais un rejet silencieux ici)."""
    n = len(matchs_role)

    stats_off = team_stats.stats_offensives(matchs_role)
    stats_def = team_stats.stats_defensives(matchs_role)
    resultats = team_stats.resultats(matchs_role)
    r_btts = goals.btts(matchs_role)
    r_over25 = goals.over_under(matchs_role, 2.5)

    buts_marques = [m["buts_marques"] for m in matchs_role]
    buts_encaisses = [m["buts_encaisses"] for m in matchs_role]
    marges = [m["buts_marques"] - m["buts_encaisses"] for m in matchs_role]

    return {
        "n": n,
        "statut_fiabilite": STATUT_FIABLE if n >= N_MIN_PROFIL_FIABLE else STATUT_A_SURVEILLER,
        "poids_fiabilite": poids_fiabilite(n),

        "attaque": {
            "moyenne": stats_off["moyenne"],
            "regularite_cv": _coefficient_variation(stats_off["moyenne"], stats_off["ecart_type"]),
            "freq_marque_0": _frequence_egale(buts_marques, 0),
            "freq_marque_1_plus": _frequence_seuil(buts_marques, 1),
            "freq_marque_2_plus": _frequence_seuil(buts_marques, 2),
            "musique": _musique(buts_marques),
            "serie_marque_actuelle": _serie_actuelle(matchs_role, lambda m: m["buts_marques"] >= 1),
            "serie_sans_marquer_actuelle": _serie_actuelle(matchs_role, lambda m: m["buts_marques"] == 0),
        },
        "defense": {
            "moyenne": stats_def["moyenne"],
            "regularite_cv": _coefficient_variation(stats_def["moyenne"], stats_def["ecart_type"]),
            "freq_clean_sheet": stats_def["frequence_clean_sheets"],
            "freq_encaisse_2_plus": _frequence_seuil(buts_encaisses, 2),
            "musique": _musique(buts_encaisses),
            "serie_clean_sheet_actuelle": _serie_actuelle(matchs_role, lambda m: m["buts_encaisses"] == 0),
            "serie_encaisse_actuelle": _serie_actuelle(matchs_role, lambda m: m["buts_encaisses"] >= 1),
        },
        "resultats": {
            "freq_victoires": resultats["frequence_victoires"],
            "freq_nuls": resultats["frequence_nuls"],
            "freq_defaites": resultats["frequence_defaites"],
            "marge_buts_moyenne": moyenne(marges),
            "marge_buts_ecart_type": ecart_type(marges),
            "forme_ponderee_recence": _forme_ponderee_recence(matchs_role),
        },
        "tendances_buts": {
            "freq_btts": r_btts["frequence"],
            "freq_over_2_5": r_over25["frequence_over"],
        },
    }
