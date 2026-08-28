"""
calculs.py — Portage déterministe des Règles N3 / N4 / N6 / N7 (Module 2 v4.3)
et de l'Étape 7 (Module 3 v6.3), UNIQUEMENT la partie mathématique fixe.

Ce fichier N'IMPLÉMENTE PAS :
- la vérification de fraîcheur des pages sources (Module 1)
- la détection de pénalités de points (Module 1)
- le risque de rotation continentale (Module 1 v1.7)
- la double vérification des handicaps 3 voies (Module 3, Étape 4)
- toute analyse de corrélation sémantique entre marchés (nécessite jugement,
  pas juste un chiffre — cf. SEUIL_CORRELATION ci-dessous, implémenté seulement
  pour le cas simple "même match, marchés mécaniquement liés")

Ces points restent des tâches manuelles ou une v2 — les inclure de façon fiable
avant demain reviendrait à réécrire en code un jugement d'agent, pas juste une formule.

Constantes reprises telles quelles de TABLEAU_RECAPITULATIF.md (gelées jusqu'à
backtest historique — ne pas modifier sans repasser par ce document).
"""

import math

# --- Constantes gelées (Module 2 / Module 3) ---
GA_REFERENCE = 1.35
BORNE_MIN_DEFENSE = 0.70
BORNE_MAX_DEFENSE = 1.30

POIDS_FORME = 0.30
POIDS_CLASSEMENT = 0.20
POIDS_REPOS = 0.15
POIDS_ABSENCES = 0.15
POIDS_DISTANCE = 0.10
POIDS_H2H = 0.10
BORNE_RATIO = 0.15  # borne +/- par facteur avant pondération

RHO_DIXON_COLES = -0.1

SEUIL_EV_MIN = 0.05
FOURCHETTE_COTE_MIN = 1.25
FOURCHETTE_COTE_MAX = 1.69
SEUIL_CORRELATION = 0.70
KELLY_FRACTION = 0.25
MISE_MAX_PARI = 0.04
CLUSTER_MAX = 0.10
NB_PARIS_MAX = 3
SEUIL_STANDOUT = 0.15

CONFIANCE_LAMBDA_SEUILS = {"FAIBLE": 8, "MOYENNE": 15}  # < 8 = FAIBLE, < 15 = MOYENNE, sinon NORMALE


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


# --------------------------------------------------------------------------
# Étape 3 (Module 2 v4.3) — ratios contextuels. Forme, Absences, Distance
# ANNULÉS sur décision explicite (25/08) : Forme jamais formalisée sur ce
# projet, Absences non fiable à scraper sur matchendirect (pas de liste
# blessés/suspendus confirmée), Distance jamais commencée (géocodage).
# Seuls Classement et H2H sont calculés. Le garde-fou "donnée absente ->
# ratio neutre (0.0)" du Module 2 s'applique aux deux -- jamais une erreur,
# jamais une estimation devinée.
# --------------------------------------------------------------------------

def _normalise_texte_ratio(s):
    import re
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _memes_equipes_ratio(nom1, nom2):
    n1, n2 = _normalise_texte_ratio(nom1), _normalise_texte_ratio(nom2)
    return n1 == n2 or n1 in n2 or n2 in n1


def calcule_ratio_classement(classement, nom_equipe, nom_adversaire):
    """
    Score_classement = (N-Position)/(N-1)
    ratio_classement = clamp(Score_propre - Score_adverse, -0.15, 0.15)
    `classement` : liste renvoyée par recupere_classement_du_match
    (scraper_details.py), déjà triée par rang (ordre du document = ordre
    d'affichage du site -- position = index + 1).
    """
    N = len(classement)
    if N <= 1:
        return 0.0

    def position_de(nom):
        for i, ligne in enumerate(classement):
            if _memes_equipes_ratio(ligne.get("equipe", ""), nom):
                return i + 1
        return None

    pos_propre = position_de(nom_equipe)
    pos_adverse = position_de(nom_adversaire)
    if pos_propre is None or pos_adverse is None:
        return 0.0

    score_propre = (N - pos_propre) / (N - 1)
    score_adverse = (N - pos_adverse) / (N - 1)
    return clamp(score_propre - score_adverse, -0.15, 0.15)


def calcule_ratio_h2h(historique_h2h, nom_equipe, nom_adversaire, max_confrontations=10):
    """
    ratio_h2h = clamp((moyenne_propre - moyenne_adverse)/3, -0.15, 0.15)
    sur les 10 dernières confrontations directes disponibles (ou moins si
    l'historique est plus court). `historique_h2h` : sortie de
    recupere_h2h (scraper_details.py), plus récent en premier.
    """
    buts_propre, buts_adverse = [], []
    for m in historique_h2h[:max_confrontations]:
        if _memes_equipes_ratio(nom_equipe, m.get("domicile_brut", "")):
            buts_propre.append(m["buts_domicile"])
            buts_adverse.append(m["buts_exterieur"])
        elif _memes_equipes_ratio(nom_equipe, m.get("exterieur_brut", "")):
            buts_propre.append(m["buts_exterieur"])
            buts_adverse.append(m["buts_domicile"])

    if not buts_propre:
        return 0.0

    moyenne_propre = sum(buts_propre) / len(buts_propre)
    moyenne_adverse = sum(buts_adverse) / len(buts_adverse)
    return clamp((moyenne_propre - moyenne_adverse) / 3, -0.15, 0.15)


# --------------------------------------------------------------------------
# Module 3 v6.3 — Étapes 1, 2, 4, 6 (25/08). Handicap 3 voies (Étape 0) EXCLU
# sur décision explicite. Rotation continentale EXCLUE. Le dimensionnement
# Kelly (Étape 7, déjà existant ci-dessus) reste strictement inchangé.
# --------------------------------------------------------------------------

def correlation_marches(matrice, condition_a, condition_b):
    """
    Corrélation de Pearson EXACTE entre deux indicatrices de marché, calculée
    sur la matrice jointe Poisson/Dixon-Coles déjà produite pour le match --
    un calcul mécanique déterminé par le modèle lui-même, pas une estimation
    ni un jugement sémantique. Sert à éviter d'empiler des mises sur des
    marchés redondants du MÊME match (Étape 4, Module 3 v6.3).
    """
    scores = list(matrice.keys())
    probs = list(matrice.values())
    a = [1.0 if condition_a(x, y) else 0.0 for (x, y) in scores]
    b = [1.0 if condition_b(x, y) else 0.0 for (x, y) in scores]

    ea = sum(p*ai for p, ai in zip(probs, a))
    eb = sum(p*bi for p, bi in zip(probs, b))
    cov = sum(p*(ai-ea)*(bi-eb) for p, ai, bi in zip(probs, a, b))
    var_a = sum(p*(ai-ea)**2 for p, ai in zip(probs, a))
    var_b = sum(p*(bi-eb)**2 for p, bi in zip(probs, b))

    if var_a <= 0 or var_b <= 0:
        return 0.0
    return cov / math.sqrt(var_a * var_b)


def construit_liste_a(candidats_bruts, seuil_ev=SEUIL_EV_MIN,
                       cote_min=FOURCHETTE_COTE_MIN, cote_max=FOURCHETTE_COTE_MAX):
    """
    Étapes 1-2 Module 3 : plancher EV (5%) puis fourchette de cote
    (1.25-1.69). `candidats_bruts` : liste de dicts
    {"marche", "condition" (fn(x,y)->bool), "probabilite_modele", "cote_observee"}.
    Retourne LISTE_A, triée par EV décroissant. Un candidat sans cote
    (cote_observee=None) est écarté silencieusement, jamais une erreur.
    """
    liste_a = []
