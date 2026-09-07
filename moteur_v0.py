"""
moteur_v0.py — Moteur de pronostic V0 (décision explicite de Patrick, 07/09/2026).

CONTEXTE -- pourquoi ce fichier existe séparément de calculs.py/run_pipeline.py/
adapte_justification.py : la session du 07/09 a mis au jour que plusieurs
constantes du moteur existant (K_SHRINKAGE=0.48, K_SHRINKAGE_LAMBDA=3) sont
des réglages provisoires dérivés d'un échantillon minuscule (63 paris sur 9
jours), jamais un backtest réel -- et qu'un bug d'orientation H2H dans la
justification affichée (adapte_justification.py, corrigé le 07/09 pour les
marchés OVER_UNDER_EQUIPE/CLEAN_SHEET/SANS_BUT mais jamais pour 1X2/Double
chance) montrait qu'empiler des raffinements sans les vérifier un par un
rend le système difficile à auditer.

Décision : ne PAS corriger encore une pièce du moteur existant. Reconstruire
un moteur V0 volontairement simple, avec le moins de paramètres possible,
CHACUN explicitement déclaré et justifié -- pour ensuite le faire tourner en
parallèle (SANS ARGENT RÉEL), logger absolument tout résultat (GO et NO_GO),
et ne calibrer une V1 que sur la base de résultats réels observés.

Ce fichier NE MODIFIE RIEN dans calculs.py / run_pipeline.py /
adapte_justification.py / precalcul.py -- le moteur existant continue de
tourner tel quel. Réutilise uniquement les briques déjà testées et non
remises en cause (matrice_poisson_dixon_coles avec rho=0 forcé en V0,
calcule_roi.verifie_pari, GA_REFERENCE_PAR_LIGUE/PAR_COMPETITION -- mais
seulement leurs valeurs RÉELLEMENT mesurées, jamais leur "default").

===============================================================================
CONSTANTES DE CONCEPTION V0 -- décidées explicitement le 07/09/2026, à ne
JAMAIS modifier sans repasser par une décision de Patrick documentée ici.
===============================================================================

    N_MIN = 8
        Veto dur (Étape "DONNÉES"). En dessous de 8 matchs exploitables
        (domicile ou extérieur), NO_BET automatique. Pas de compensation.

    LAMBDA_MIN_PLAUSIBLE = 0.1 / LAMBDA_MAX_PLAUSIBLE = 6.0
        GARDE-FOU D'INTÉGRITÉ MATHÉMATIQUE, PAS UN PARAMÈTRE DE CALIBRATION.
        Ne détecte pas "un mauvais pari" -- détecte un résultat statistiquement
        impossible en football pro (cas réel qui a motivé cette borne dans le
        moteur existant : Vaduz II, n=1, un seul match 8-0, lambda=12.8).
        Ne JAMAIS le confondre dans un audit futur avec EV_MIN/STAKE_V0
        ci-dessous, qui EUX sont des réglages à calibrer.

    EV_MIN = 0.05 (+5%)
        PROVISOIRE, NON CALIBRÉ. Garde-fou expérimental contre le bruit de
        décision sur un modèle non encore validé -- volontairement plus haut
        que le 2% du moteur existant, pour la même raison que ce dernier
        s'est révélé insuffisant (un edge de quelques points de % n'est pas
        distinguable du bruit d'estimation sur N=8-10 matchs). À recalibrer
        uniquement sur la base d'un historique réel (voir historique_v0.jsonl).

    STAKE_V0 = 0.01 (1% bankroll fixe)
        PROVISOIRE. Mise fixe, PAS Kelly, PAS proportionnelle à l'EV ou à la
        probabilité. Tant que le modèle n'est pas démontré calibré, il ne
        doit pas déterminer lui-même son exposition financière.

    RHO_DIXON_COLES_V0 = 0.0
        Pas de correction Dixon-Coles sur les scores bas en V0. La valeur
        -0.1 utilisée par le moteur existant (RHO_DIXON_COLES dans
        calculs.py) est elle-même une constante jamais recalibrée sur ce
        projet -- même principe que les autres raffinements retirés : on ne
        l'introduit que si un backtest futur démontre qu'elle aide.

    Formule de lambda -- PAS de shrinkage bayésien, PAS de "default" de
    référence de ligue (voir doctrine complète sur calcule_lambda_v0
    ci-dessous) :
        lambda_brut = (attaque_propre_moyenne + defense_adverse_moyenne) / 2
        Ajustement par référence de ligue UNIQUEMENT si une valeur RÉELLEMENT
        MESURÉE existe pour ce pays/cette compétition (voir
        get_reference_verifiee) -- sinon modificateur neutre (1.0), JAMAIS
        de "default"=1.35 inventé, JAMAIS de blocage NO_BET pour ce seul motif.

    Aucun seuil de probabilité minimale (décision explicite -- une
    probabilité seule ne dit rien sans la cote en face).
    Aucun score composite (pas de "Convergence", "Fiabilité", "Robustesse"
    pondérés) -- verdict par vetos successifs uniquement.
    Aucun veto sur la divergence avec la cote du marché -- observée et
    loggée, jamais bloquante en V0 (pourra le devenir en V1 si démontré utile).
"""

import math
from typing import Optional

import calcule_roi
from calculs import (
    GA_REFERENCE_PAR_LIGUE,
    GA_REFERENCE_PAR_COMPETITION,
    probabilite_marche,
    probabilite_double_chance,
    probabilite_over_under,
    probabilite_btts,
    probabilite_handicap_2choix,
    probabilite_pair_impair,
    probabilite_cages_inviolees,
)

MAX_BUTS_V0 = 15  # même borne que le moteur existant -- masse au-delà négligeable (~1e-4) même à lambda=10

# --- Constantes V0 (voir doctrine complète en tête de fichier) ---
N_MIN = 8
LAMBDA_MIN_PLAUSIBLE = 0.1
LAMBDA_MAX_PLAUSIBLE = 6.0
EV_MIN = 0.05
STAKE_V0 = 0.01
RHO_DIXON_COLES_V0 = 0.0

LIGNES_OU = (0.5, 1.5, 2.5, 3.5, 4.5)
LIGNES_HANDICAP = (-2.5, -1.5, -0.5, 0.5, 1.5, 2.5)

# --------------------------------------------------------------------------
# Familles de marchés (décision Patrick, 07/09/2026) -- un seul candidat
# retenu par famille, jamais deux qui racontent le même scénario.
# --------------------------------------------------------------------------
FAMILLES_MARCHES = {
    "total_buts": [f"Plus de {l} buts" for l in LIGNES_OU] + [f"Moins de {l} buts" for l in LIGNES_OU],
    "buts_domicile": [f"Plus de {l} buts - Domicile" for l in LIGNES_OU] + [f"Moins de {l} buts - Domicile" for l in LIGNES_OU],
    "buts_exterieur": [f"Plus de {l} buts - Extérieur" for l in LIGNES_OU] + [f"Moins de {l} buts - Extérieur" for l in LIGNES_OU],
    "resultat": ["1X2 - 1", "1X2 - X", "1X2 - 2",
                 "Double chance - 1X", "Double chance - 12", "Double chance - X2"],
    "handicap": [f"Handicap {l} - Domicile" for l in LIGNES_HANDICAP] + [f"Handicap {l} - Extérieur" for l in LIGNES_HANDICAP],
}


def _famille_de(marche: str) -> str:
    """Renvoie le nom de famille du marché, ou le marché lui-même si aucune
    famille ne le contient (BTTS, Pair/Impair, Cage inviolée, Sans but,
    Score exact -- familles indépendantes, un seul candidat par nature)."""
    for famille, marches in FAMILLES_MARCHES.items():
        if marche in marches:
            return famille
    return marche


# --------------------------------------------------------------------------
# Étape 1 -- contrôle des données (N_MIN, veto dur)
# --------------------------------------------------------------------------

def controle_donnees(nb_matchs_domicile_utilises: int, nb_matchs_exterieur_utilises: int) -> Optional[str]:
    """Renvoie None si éligible, sinon le motif de NO_BET."""
    if nb_matchs_domicile_utilises < N_MIN:
        return f"Échantillon domicile insuffisant ({nb_matchs_domicile_utilises} match(s) < {N_MIN})"
    if nb_matchs_exterieur_utilises < N_MIN:
        return f"Échantillon extérieur insuffisant ({nb_matchs_exterieur_utilises} match(s) < {N_MIN})"
    return None


# --------------------------------------------------------------------------
# Étape 2 -- lambda (formule figée, voir doctrine en tête de fichier)
# --------------------------------------------------------------------------

def get_reference_verifiee(pays: Optional[str] = None, competition: Optional[str] = None) -> Optional[float]:
    """Référence défensive de ligue -- UNIQUEMENT si une valeur réellement
    mesurée existe (jamais "default"=1.35, qui est une estimation non
    vérifiée, pas une mesure). Renvoie None si aucune valeur mesurée
    n'existe pour ce pays/cette compétition -- l'appelant doit alors
    appliquer un modificateur neutre (1.0), jamais bloquer le match pour ce
    seul motif (décision explicite de Patrick, 07/09/2026 : "on ne peut pas
    ignorer tout le monde")."""
    if competition is not None and competition in GA_REFERENCE_PAR_COMPETITION:
        return GA_REFERENCE_PAR_COMPETITION[competition]
    if pays is not None and pays in GA_REFERENCE_PAR_LIGUE and pays != "default":
        return GA_REFERENCE_PAR_LIGUE[pays]
    return None


def calcule_lambda_v0(gf_home_domicile, ga_home_domicile, gf_away_exterieur, ga_away_exterieur,
                       pays=None, competition=None):
    """
    lambda_domicile = (gf_home_domicile + ga_away_exterieur) / 2 * modificateur_defense
    lambda_exterieur = (gf_away_exterieur + ga_home_domicile) / 2 * modificateur_defense

    Pas de shrinkage bayésien vers une référence (décision V0 : on assume le
    bruit d'un petit échantillon, compensé par le veto N_MIN, pas par une
    correction de lambda). Le modificateur de référence de ligue n'est
    appliqué QUE si get_reference_verifiee() renvoie une vraie valeur ;
    sinon il vaut 1.0 (neutre, aucun ajustement, jamais un blocage).

    CORRECTIF (audit du 07/09/2026, demandé par Patrick) : le modificateur
    n'est plus borné par un clamp intermédiaire -- une version précédente
    empruntait BORNE_MIN/MAX_DEFENSE au moteur existant (0.55/1.60, avec en
    plus une erreur de recopie à 0.5/1.5) sans jamais faire valider cette
    constante. Retiré entièrement : le veto de plausibilité sur le lambda
    FINAL (verifie_plausibilite_lambda, 0.1-6.0, déjà approuvé) est le seul
    filet de sécurité -- un modificateur extrême produirait un lambda hors
    plage, intercepté en aval, sans besoin d'un deuxième garde-fou non
    déclaré.
    """
    reference = get_reference_verifiee(pays, competition)

    lambda_domicile_brut = (gf_home_domicile + ga_away_exterieur) / 2
    lambda_exterieur_brut = (gf_away_exterieur + ga_home_domicile) / 2

    if reference is not None and reference > 0:
        modifier_domicile = ga_away_exterieur / reference
        modifier_exterieur = ga_home_domicile / reference
    else:
        modifier_domicile = 1.0
        modifier_exterieur = 1.0

    return {
        "lambda_home": lambda_domicile_brut * modifier_domicile,
        "lambda_away": lambda_exterieur_brut * modifier_exterieur,
        "audit": {
            "lambda_home_brut": lambda_domicile_brut,
            "lambda_away_brut": lambda_exterieur_brut,
            "reference_utilisee": reference,
            "modifier_domicile": modifier_domicile,
            "modifier_exterieur": modifier_exterieur,
        },
    }


def verifie_plausibilite_lambda(lambda_home: float, lambda_away: float) -> Optional[str]:
    """Garde-fou d'intégrité (voir doctrine) -- renvoie None si plausible,
    sinon le motif de NO_BET."""
    if not (math.isfinite(lambda_home) and math.isfinite(lambda_away)):
        return f"Lambda non fini (domicile={lambda_home}, extérieur={lambda_away})"
    if not (LAMBDA_MIN_PLAUSIBLE <= lambda_home <= LAMBDA_MAX_PLAUSIBLE):
        return f"Lambda domicile hors plage plausible ({lambda_home:.2f}, attendu {LAMBDA_MIN_PLAUSIBLE}-{LAMBDA_MAX_PLAUSIBLE})"
    if not (LAMBDA_MIN_PLAUSIBLE <= lambda_away <= LAMBDA_MAX_PLAUSIBLE):
        return f"Lambda extérieur hors plage plausible ({lambda_away:.2f}, attendu {LAMBDA_MIN_PLAUSIBLE}-{LAMBDA_MAX_PLAUSIBLE})"
    return None


# --------------------------------------------------------------------------
# Étape 3 -- matrice Poisson (Dixon-Coles désactivé en V0, rho=0.0)
# --------------------------------------------------------------------------

def matrice_poisson_v0(lambda_home: float, lambda_away: float, max_buts: int = MAX_BUTS_V0):
    """Produit de deux lois de Poisson indépendantes, SANS correction
    Dixon-Coles (RHO_DIXON_COLES_V0 = 0.0 -- voir doctrine en tête de
    fichier). Implémentation locale plutôt qu'un appel à
    calculs.matrice_poisson_dixon_coles : cette dernière n'expose pas rho
    en paramètre (constante globale interne au fichier, RHO_DIXON_COLES=
    -0.1) -- l'appeler telle quelle appliquerait silencieusement la
    correction du moteur existant, jamais validée sur ce projet, exactement
    ce qu'on s'interdit en V0. Mathématiquement équivalent à
    matrice_poisson_dixon_coles(..., rho=0) : la correction Dixon-Coles à
    rho=0 vaut identiquement 1.0 sur les 4 cases qu'elle module."""

    def poisson_pmf(k, lam):
        return (lam ** k) * math.exp(-lam) / math.factorial(k)

    matrice = {}
    for x in range(max_buts + 1):
        for y in range(max_buts + 1):
            matrice[(x, y)] = poisson_pmf(x, lambda_home) * poisson_pmf(y, lambda_away)

    total = sum(matrice.values())
    if total > 0:
        matrice = {k: v / total for k, v in matrice.items()}
    return matrice


def probabilites_marches_v0(matrice):
    """Construit toutes les probabilités modèle utiles à la V0. Structure
    à plat (une entrée par marché exact, libellé identique à
    calcule_roi._REGLES) -- plus simple à parcourir pour la cohérence et
    les familles que la structure imbriquée de calculs.construit_probabilites_marches."""
    marches = {}

    p_1x2 = {
        "1X2 - 1": probabilite_marche(matrice, lambda x, y: x > y),
        "1X2 - X": probabilite_marche(matrice, lambda x, y: x == y),
        "1X2 - 2": probabilite_marche(matrice, lambda x, y: x < y),
    }
    marches.update(p_1x2)

    p_dc = probabilite_double_chance(matrice)
    marches["Double chance - 1X"] = p_dc["1X"]
    marches["Double chance - 12"] = p_dc["12"]
    marches["Double chance - X2"] = p_dc["X2"]

    p_btts = probabilite_btts(matrice)
    marches["BTTS - oui"] = p_btts["oui"]
    marches["BTTS - non"] = p_btts["non"]

    p_pi = probabilite_pair_impair(matrice)
    marches["Total buts - pair"] = p_pi["pair"]
    marches["Total buts - impair"] = p_pi["impair"]

    p_ci_dom = probabilite_cages_inviolees(matrice, "home")
    p_ci_ext = probabilite_cages_inviolees(matrice, "away")
    marches["Cage inviolée - Domicile"] = p_ci_dom["oui"]
    marches["Cage inviolée - Extérieur"] = p_ci_ext["oui"]
    marches["Encaisse au moins 1 but - Domicile"] = p_ci_ext["non"]  # domicile encaisse <=> ext marque
    marches["Encaisse au moins 1 but - Extérieur"] = p_ci_dom["non"]

    for ligne in LIGNES_OU:
        ou = probabilite_over_under(matrice, ligne)
        marches[f"Plus de {ligne} buts"] = ou["plus"]
        marches[f"Moins de {ligne} buts"] = 1 - ou["plus"]  # complémentaire strict, cohérent par construction

        ou_dom = probabilite_over_under(matrice, ligne, "home")
        marches[f"Plus de {ligne} buts - Domicile"] = ou_dom["plus"]
        marches[f"Moins de {ligne} buts - Domicile"] = 1 - ou_dom["plus"]

        ou_ext = probabilite_over_under(matrice, ligne, "away")
        marches[f"Plus de {ligne} buts - Extérieur"] = ou_ext["plus"]
        marches[f"Moins de {ligne} buts - Extérieur"] = 1 - ou_ext["plus"]

    for ligne in LIGNES_HANDICAP:
        h = probabilite_handicap_2choix(matrice, ligne)
        marches[f"Handicap {ligne} - Domicile"] = h["domicile"]
        marches[f"Handicap {ligne} - Extérieur"] = h["exterieur"]

    return marches


# --------------------------------------------------------------------------
# Étape 4 -- contrôle de cohérence (veto structurel, sans coefficient)
# --------------------------------------------------------------------------

def verifie_coherence_v0(marches_probas):
    """Vérifie les relations mathématiques obligatoires. Ne corrige jamais
    -- si une ligne viole la monotonie attendue par rapport à la ligne
    juste en dessous, cette ligne (la plus haute des deux, celle dont la
    valeur est incohérente) est marquée invalidée. Renvoie l'ensemble des
    libellés de marché à exclure de la sélection.

    Relations vérifiées :
    - Plus de X buts (total/domicile/extérieur) : probabilité strictement
      décroissante quand X augmente.
    - Handicap - Domicile : probabilité de couverture croissante quand la
      ligne (favorable au domicile) augmente.
    """
    invalides = set()

    for prefixe_libelle, gabarit in (
        ("", "Plus de {l} buts"),
        (" - Domicile", "Plus de {l} buts - Domicile"),
        (" - Extérieur", "Plus de {l} buts - Extérieur"),
    ):
        precedente = None
        for ligne in LIGNES_OU:
            cle = gabarit.format(l=ligne)
            valeur = marches_probas.get(cle)
            if valeur is None:
                continue
            if precedente is not None and valeur > precedente + 1e-9:
                invalides.add(cle)
                invalides.add(gabarit.format(l=ligne).replace("Plus de", "Moins de"))
            else:
                precedente = valeur

    precedente = None
    for ligne in LIGNES_HANDICAP:
        cle = f"Handicap {ligne} - Domicile"
        valeur = marches_probas.get(cle)
        if valeur is None:
            continue
        if precedente is not None and valeur < precedente - 1e-9:
            invalides.add(cle)
            invalides.add(f"Handicap {ligne} - Extérieur")
        else:
            precedente = valeur

    return invalides


# --------------------------------------------------------------------------
# Étape 5 -- contrôle empirique (observation descriptive uniquement, jamais
# mélangée à la probabilité modèle -- décision explicite du 07/09/2026)
# --------------------------------------------------------------------------

# Marchés SYMÉTRIQUES -- leur vérification (verifie_pari) ne dépend QUE de
# x+y, ou de x>0 et y>0 indépendamment, jamais de la position réelle
# domicile/extérieur. Ce sont les SEULS marchés qu'on peut évaluer
# honnêtement sur l'historique "propre" d'une équipe (buts_marques/
# buts_encaisses, déjà réorienté du point de vue de l'équipe elle-même, PAS
# les vraies positions domicile/extérieur du match réel).
#
# CORRECTIF (audit du 07/09/2026, demandé par Patrick) : la version
# précédente appelait verifie_pari(marche, buts_marques, buts_encaisses)
# pour TOUS les marchés sans exception -- correct pour les symétriques,
# mais FAUX pour 1X2/Double chance/Handicap/"- Domicile"/"- Extérieur"/Cage
# inviolée/Encaisse au moins 1 but/Score exact : ces marchés dépendent de
# la position (x=domicile réel, y=extérieur réel) que verifie_pari attend,
# alors que buts_marques/buts_encaisses n'est PAS cette position -- c'est
# le même bug d'orientation que celui trouvé et corrigé le 07/09 dans
# adapte_justification.py (bug #41), réintroduit ici par erreur puis
# retrouvé pendant l'audit ligne par ligne demandé par Patrick le même
# jour. Restreint désormais aux marchés dont verifie_pari a été vérifié
# commutatif par construction (voir adapte_justification.MARCHES_SYMETRIQUES,
# même liste conceptuelle, redéfinie ici localement pour ne pas créer de
# dépendance croisée entre les deux fichiers).
_MARCHES_SYMETRIQUES_EMPIRIQUE = {
    "BTTS - oui", "BTTS - non",
    "Total buts - pair", "Total buts - impair",
} | {f"Plus de {l} buts" for l in LIGNES_OU} | {f"Moins de {l} buts" for l in LIGNES_OU}


def controle_empirique_v0(marche: str, matchs_domicile_bruts, matchs_exterieur_bruts, cible: str):
    """cible : 'domicile' ou 'exterieur' -- sur quel historique observer le
    marché. Renvoie (occurrences, total) ou None si non observable OU si le
    marché n'est pas symétrique (voir _MARCHES_SYMETRIQUES_EMPIRIQUE --
    jamais une observation orientée à tort). Réutilise calcule_roi.verifie_pari
    tel quel (même règle de marché que partout ailleurs dans le dépôt --
    jamais une deuxième définition)."""
    if marche not in _MARCHES_SYMETRIQUES_EMPIRIQUE:
        return None
    matchs = matchs_domicile_bruts if cible == "domicile" else matchs_exterieur_bruts
    if not matchs:
        return None
    occurrences, total = 0, 0
    for m in matchs:
        # matchs bruts orientés "propre" (buts_marques/buts_encaisses) --
        # verifie_pari attend (buts_domicile, buts_exterieur) : on ne peut
        # évaluer honnêtement ainsi que les marchés symétriques ou orientés
        # "propre" via la forme sans suffixe -- limite documentée, pas
        # contournée.
        resultat = calcule_roi.verifie_pari(marche, m["buts_marques"], m["buts_encaisses"])
        if resultat is None:
            continue
        total += 1
        if resultat:
            occurrences += 1
    if total == 0:
        return None
    return occurrences, total


# --------------------------------------------------------------------------
# Étape 6 -- cote, valeur (EV), décision
# --------------------------------------------------------------------------

def calcule_ev_v0(probabilite_modele: float, cote_observee: float) -> Optional[float]:
    """EV = P_modele * cote - 1. Pas de shrinkage (décision V0)."""
    if cote_observee is None:
        return None
    return probabilite_modele * cote_observee - 1


def probabilite_implicite_marche(cote_observee: float) -> Optional[float]:
    """Probabilité implicite BRUTE (marge du bookmaker incluse) -- simple
    inverse de la cote. Pas de retrait de marge en V0 (nécessiterait les
    cotes des issues complémentaires du même marché, pas toujours
    disponibles ici) -- affiché/loggé tel quel, jamais utilisé comme veto."""
    if not cote_observee:
        return None
    return 1 / cote_observee


def filtre_famille_v0(candidats):
    """Un seul candidat retenu par famille -- le meilleur EV. `candidats` :
    liste de dicts contenant au moins {"marche", "ev"}."""
    meilleur_par_famille = {}
    for c in candidats:
        famille = _famille_de(c["marche"])
        actuel = meilleur_par_famille.get(famille)
        if actuel is None or c["ev"] > actuel["ev"]:
            meilleur_par_famille[famille] = c
    return list(meilleur_par_famille.values())


def evalue_match_v0(gf_home_domicile, ga_home_domicile, gf_away_exterieur, ga_away_exterieur,
                     nb_matchs_domicile_utilises, nb_matchs_exterieur_utilises,
                     cotes_marches: dict,
                     matchs_domicile_bruts=None, matchs_exterieur_bruts=None,
                     pays=None, competition=None):
    """
    Point d'entrée unique du moteur V0. `cotes_marches` : dict {libellé
    marché exact (voir FAMILLES_MARCHES / calcule_roi._REGLES) -> cote ou
    None}. Renvoie un dict complet -- TOUJOURS, GO ou NO_GO -- destiné à
    être loggé intégralement (voir historique_v0.jsonl).
    """
    matchs_domicile_bruts = matchs_domicile_bruts or []
    matchs_exterieur_bruts = matchs_exterieur_bruts or []

    resultat = {
        "verdict": "NO_BET",
        "motif": None,
        "lambda_home": None,
        "lambda_away": None,
        "marches_evalues": [],
        "selection": [],
    }

    motif = controle_donnees(nb_matchs_domicile_utilises, nb_matchs_exterieur_utilises)
    if motif:
        resultat["motif"] = motif
        return resultat

    lam = calcule_lambda_v0(gf_home_domicile, ga_home_domicile, gf_away_exterieur, ga_away_exterieur,
                             pays=pays, competition=competition)
    resultat["lambda_home"] = lam["lambda_home"]
    resultat["lambda_away"] = lam["lambda_away"]
    resultat["lambda_audit"] = lam["audit"]

    motif = verifie_plausibilite_lambda(lam["lambda_home"], lam["lambda_away"])
    if motif:
        resultat["motif"] = motif
        return resultat

    matrice = matrice_poisson_v0(lam["lambda_home"], lam["lambda_away"])
    marches_probas = probabilites_marches_v0(matrice)
    marches_invalides = verifie_coherence_v0(marches_probas)

    candidats_go = []
    for marche, proba in marches_probas.items():
        cote = cotes_marches.get(marche)
        coherent = marche not in marches_invalides
        ev = calcule_ev_v0(proba, cote) if (cote and coherent) else None
        empirique_dom = controle_empirique_v0(marche, matchs_domicile_bruts, matchs_exterieur_bruts, "domicile")
        empirique_ext = controle_empirique_v0(marche, matchs_domicile_bruts, matchs_exterieur_bruts, "exterieur")

        entree = {
            "marche": marche,
            "probabilite_modele": proba,
            "cote": cote,
            "probabilite_implicite_marche": probabilite_implicite_marche(cote) if cote else None,
            "ev": ev,
            "coherent": coherent,
            "empirique_domicile": empirique_dom,
            "empirique_exterieur": empirique_ext,
            "famille": _famille_de(marche),
        }
        resultat["marches_evalues"].append(entree)

        # Tolérance flottante explicite (1e-9) -- sans elle, un pari
        # mathématiquement pile au seuil (ex. 0.70*1.5-1 = 0.05) peut être
        # rejeté à tort : en float, ce calcul vaut 0.049999999999999822,
        # pas 0.05 exact (trouvé en test le 07/09/2026). La tolérance ne
        # change jamais un rejet légitime (EV réellement sous le seuil,
        # ex. 4.99%) en acceptation -- 1e-9 est très inférieur à toute
        # différence significative entre deux probabilités/cotes réelles.
        if coherent and ev is not None and ev >= EV_MIN - 1e-9:
            candidats_go.append(entree)

    selection = filtre_famille_v0(candidats_go)
    for s in selection:
        s["mise_pct_bankroll"] = STAKE_V0

    resultat["selection"] = selection
    resultat["verdict"] = "GO" if selection else "NO_GO"
    if not selection:
        resultat["motif"] = (
            f"{len(resultat['marches_evalues'])} marché(s) évalués, "
            f"aucun avec EV >= {EV_MIN*100:.0f}% après contrôle de cohérence"
        )
    return resultat


# --------------------------------------------------------------------------
# Traçabilité -- GO et NO_GO/NO_BET, dès le premier jour (décision Patrick,
# 07/09/2026 : le moteur existant n'archivait que ce qui passait déjà le
# filtre EV, plafonnant son échantillon de calibration à 63 paris).
# --------------------------------------------------------------------------

import json
import datetime


def enregistre_evaluation_v0(match_info: dict, resultat: dict, chemin: str = "historique_v0.jsonl"):
    """Ajoute une ligne JSON par match évalué (GO, NO_GO ou NO_BET), avec
    toutes les entrées et le verdict. `resultat_reel` reste None -- à
    remplir plus tard, une fois le match joué, pour permettre le futur
    backtest (jamais un champ deviné ici). `match_info` : dict libre
    (ex. {"equipe_domicile":..., "equipe_exterieur":..., "competition":...,
    "date":...}) -- fourni par l'appelant, pas construit ici."""
    ligne = {
        "horodatage_evaluation": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "match": match_info,
        "verdict": resultat["verdict"],
        "motif": resultat.get("motif"),
        "lambda_home": resultat.get("lambda_home"),
        "lambda_away": resultat.get("lambda_away"),
        "lambda_audit": resultat.get("lambda_audit"),
        "marches_evalues": resultat.get("marches_evalues", []),
        "selection": resultat.get("selection", []),
        "resultat_reel": None,
    }
    with open(chemin, "a", encoding="utf-8") as f:
        f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    return ligne
