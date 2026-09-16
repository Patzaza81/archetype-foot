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


def _improbabilite_serie(longueur_serie: int, frequence_base: float | None) -> float | None:
    """Probabilité, SOUS L'HYPOTHÈSE i.i.d. (grossière mais utile comme
    repère, pas comme vérité), qu'une série de cette longueur survienne
    par pur hasard étant donné la fréquence de base DE CETTE ÉQUIPE
    elle-même (jamais une fréquence générique) -- ex. 3 clean sheets de
    suite pour une équipe qui en fait 0.3 (30%) est bien plus
    improbable (0.3^3=2.7%) que pour une équipe qui en fait 0.8
    (0.8^3=51.2%). Retourne cette probabilité brute : PLUS C'EST BAS,
    PLUS LA SÉRIE EST STATISTIQUEMENT REMARQUABLE -- ne préjuge pas de
    ce que ça implique pour le prochain match (continuation ou retour à
    la moyenne), seulement de si la série mérite l'attention. None si
    longueur 0 (rien à mesurer) ou fréquence de base indisponible."""
    if longueur_serie == 0 or frequence_base is None:
        return None
    return frequence_base ** longueur_serie


def _oscillation(valeurs: list[int]) -> float | None:
    """Amplitude moyenne de changement d'un match au suivant (|delta|)
    -- distincte de regularite_cv (dispersion globale de la
    DISTRIBUTION, indifférente à l'ordre) : un motif plateau (1-1-1-1)
    a une oscillation de 0 quelle que soit sa variance ; un motif en
    dents de scie (0-3-0-3) a une oscillation élevée même si sa
    moyenne est identique à un motif régulier à 1.5. Complète la
    régularité par la SÉQUENCE, pas seulement par la distribution.
    None si moins de 2 matchs (aucun changement mesurable)."""
    if len(valeurs) < 2:
        return None
    deltas = [abs(valeurs[i + 1] - valeurs[i]) for i in range(len(valeurs) - 1)]
    return moyenne(deltas)


def _desynchronisation_attaque_defense(cv_attaque: float | None, cv_defense: float | None) -> float | None:
    """Écart entre la régularité offensive et défensive de la MÊME
    équipe -- une équipe irrégulière en attaque mais stable en
    défense (ou l'inverse) a un profil différent d'une équipe
    uniformément régulière ou uniformément irrégulière des deux
    côtés. None si l'un des deux coefficients est indisponible."""
    if cv_attaque is None or cv_defense is None:
        return None
    return abs(cv_attaque - cv_defense)


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


# AJOUT 16/09/2026 (demande Patrick, extension du Péage 1 à des lignes
# paramétrées) -- lignes standards balayées, en plus de 2.5 qui reste
# gérée séparément ci-dessus pour ne rien casser de déjà testé.
LIGNES_OVER_UNDER_SUPPLEMENTAIRES = (1.5, 3.5)
# Mêmes 7 lignes que poisson.markets.LIGNES_HANDICAP_PAR_DEFAUT --
# dupliquées ici plutôt qu'importées pour garder ce module sans
# dépendance sur poisson/ (même principe que le reste du fichier :
# aucune dépendance nouvelle, voir docstring de module).
LIGNES_HANDICAP_PAR_DEFAUT = (-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5)


def _stats_over_under_ligne(matchs_role: list[dict[str, Any]], ligne: float) -> dict[str, Any]:
    """Généralise le bloc over/under déjà fait pour 2.5 à une ligne
    arbitraire -- même construction (freq, musique, séries), jamais
    dupliqué en dur ailleurs. Les lignes standards (1.5/2.5/3.5) sont
    toujours des demi-lignes -- une égalité exacte au total est
    impossible, freq_over + freq_under vaut donc toujours 1.0."""
    totaux = [m["buts_marques"] + m["buts_encaisses"] for m in matchs_role]
    return {
        "freq_over": _frequence_egale([1 if t > ligne else 0 for t in totaux], 1) if totaux else None,
        "freq_under": _frequence_egale([1 if t < ligne else 0 for t in totaux], 1) if totaux else None,
        "musique_over": _musique([1 if t > ligne else 0 for t in totaux]),
        "serie_over_actuelle": _serie_actuelle(matchs_role, lambda m: (m["buts_marques"] + m["buts_encaisses"]) > ligne),
        "serie_under_actuelle": _serie_actuelle(matchs_role, lambda m: (m["buts_marques"] + m["buts_encaisses"]) < ligne),
    }


def _stats_handicap_ligne(matchs_role: list[dict[str, Any]], ligne: float) -> dict[str, Any]:
    """Fréquence, pour CETTE équipe sur SON rôle, de couvrir/pousser/
    perdre un handicap à `ligne` -- même convention de signe que
    `poisson.markets.resultat_handicap` (marge = buts_marques -
    buts_encaisses ; "couvre" si marge > ligne). Ligne entière (ex.
    0.0, ±1.0) : le push (égalité exacte) est possible et compté
    séparément. Ligne demi (ex. ±0.5, ±1.5) : freq_push vaut toujours 0,
    aucun cas particulier nécessaire, la formule reste correcte."""
    marges = [m["buts_marques"] - m["buts_encaisses"] for m in matchs_role]
    if not marges:
        return {"freq_couvre": None, "freq_push": None, "freq_perd": None,
                "serie_couvre_actuelle": 0}
    return {
        "freq_couvre": sum(1 for mg in marges if mg > ligne) / len(marges),
        "freq_push": sum(1 for mg in marges if mg == ligne) / len(marges),
        "freq_perd": sum(1 for mg in marges if mg < ligne) / len(marges),
        "serie_couvre_actuelle": _serie_actuelle(matchs_role, lambda m: (m["buts_marques"] - m["buts_encaisses"]) > ligne),
    }


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

    freq_marque_0 = _frequence_egale(buts_marques, 0)
    freq_clean_sheet = stats_def["frequence_clean_sheets"]
    serie_sans_marquer = _serie_actuelle(matchs_role, lambda m: m["buts_marques"] == 0)
    serie_clean_sheet = _serie_actuelle(matchs_role, lambda m: m["buts_encaisses"] == 0)
    cv_attaque = _coefficient_variation(stats_off["moyenne"], stats_off["ecart_type"])
    cv_defense = _coefficient_variation(stats_def["moyenne"], stats_def["ecart_type"])

    return {
        "n": n,
        "statut_fiabilite": STATUT_FIABLE if n >= N_MIN_PROFIL_FIABLE else STATUT_A_SURVEILLER,
        "poids_fiabilite": poids_fiabilite(n),
        # AJOUT 16/09/2026 (demande Patrick) -- écart de régularité entre
        # attaque et défense de LA MÊME équipe (ex. attaque en dents de
        # scie, défense stable, ou l'inverse) -- pas une comparaison
        # entre deux équipes, une caractéristique interne à celle-ci.
        "desynchronisation_attaque_defense": _desynchronisation_attaque_defense(cv_attaque, cv_defense),

        "attaque": {
            "moyenne": stats_off["moyenne"],
            "regularite_cv": cv_attaque,
            "oscillation": _oscillation(buts_marques),
            "freq_marque_0": _frequence_egale(buts_marques, 0),
            "freq_marque_1_plus": _frequence_seuil(buts_marques, 1),
            "freq_marque_2_plus": _frequence_seuil(buts_marques, 2),
            "musique": _musique(buts_marques),
            "serie_marque_actuelle": _serie_actuelle(matchs_role, lambda m: m["buts_marques"] >= 1),
            "serie_sans_marquer_actuelle": serie_sans_marquer,
            "improbabilite_serie_sans_marquer": _improbabilite_serie(serie_sans_marquer, freq_marque_0),
        },
        "defense": {
            "moyenne": stats_def["moyenne"],
            "regularite_cv": cv_defense,
            "oscillation": _oscillation(buts_encaisses),
            "freq_clean_sheet": freq_clean_sheet,
            "freq_encaisse_2_plus": _frequence_seuil(buts_encaisses, 2),
            "musique": _musique(buts_encaisses),
            "serie_clean_sheet_actuelle": serie_clean_sheet,
            "serie_encaisse_actuelle": _serie_actuelle(matchs_role, lambda m: m["buts_encaisses"] >= 1),
            "improbabilite_serie_clean_sheet": _improbabilite_serie(serie_clean_sheet, freq_clean_sheet),
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
            # AJOUT 16/09/2026 (demande Patrick) -- musique appliquée aux
            # marchés dérivés eux-mêmes, pas seulement aux buts bruts :
            # une série de BTTS-oui ou d'Over-2.5 est une observation
            # différente d'une série de clean sheets, même si les deux
            # peuvent parfois coïncider sur les mêmes matchs.
            "musique_btts": _musique([1 if (m["buts_marques"] > 0 and m["buts_encaisses"] > 0) else 0 for m in matchs_role]),
            "serie_btts_oui_actuelle": _serie_actuelle(matchs_role, lambda m: m["buts_marques"] > 0 and m["buts_encaisses"] > 0),
            "serie_btts_non_actuelle": _serie_actuelle(matchs_role, lambda m: not (m["buts_marques"] > 0 and m["buts_encaisses"] > 0)),
            "musique_over_2_5": _musique([1 if (m["buts_marques"] + m["buts_encaisses"]) > 2.5 else 0 for m in matchs_role]),
            "serie_over_2_5_actuelle": _serie_actuelle(matchs_role, lambda m: (m["buts_marques"] + m["buts_encaisses"]) > 2.5),
            "serie_under_2_5_actuelle": _serie_actuelle(matchs_role, lambda m: (m["buts_marques"] + m["buts_encaisses"]) <= 2.5),
        },
        # AJOUT 16/09/2026 (demande Patrick) -- lignes Over/Under
        # supplémentaires (1.5, 3.5), clé = la ligne elle-même.
        "tendances_over_under": {
            ligne: _stats_over_under_ligne(matchs_role, ligne) for ligne in LIGNES_OVER_UNDER_SUPPLEMENTAIRES
        },
        # AJOUT 16/09/2026 (demande Patrick) -- Handicap 3 choix à
        # chaque ligne standard, clé = la ligne elle-même.
        "tendances_handicap": {
            ligne: _stats_handicap_ligne(matchs_role, ligne) for ligne in LIGNES_HANDICAP_PAR_DEFAUT
        },
    }
