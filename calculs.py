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
# GA_REFERENCE : constante externe fixe du Module 2 v4.3.
# - "Norvège"/"Suède"/"Danemark" (29/08/2026), "Italie"/"Allemagne"/
#   "France"/"Turquie"/"Espagne"/"Angleterre"/"Pays-Bas"/"Portugal"/"Grèce"/
#   "Belgique"/"Russie"/"Suisse"/"Pologne" (30/08/2026) : CALCULÉES sur
#   données réelles (Football-Data.co.uk). Saison retenue par pays -- la
#   PLUS RÉCENTE COMPLÈTE, jamais une saison en cours trop courte (le
#   Danemark 2026/2027 n'avait que 28 matchs, écart de 0.25 avec sa saison
#   complète -- même logique appliquée à Russie/Suisse/Pologne ci-dessous,
#   dont la saison 2026/2027 n'avait que 16 à 38 matchs) :
#     Italie 2025/2026 (380 matchs), Allemagne 2025/2026 (306), France
#     2025/2026 (306), Turquie 2025/2026 (306), Espagne 2025/2026 (380),
#     Angleterre 2025/2026 (380), Pays-Bas 2025/2026 (306), Portugal
#     2025/2026 (306), Grèce 2025/2026 (236), Belgique 2025/2026 (311),
#     Norvège 2025 (240), Suède 2025 (240), Danemark 2025/2026 (192),
#     Russie 2025/2026 (240), Suisse 2025/2026 (228), Pologne 2025/2026 (306).
# - "Arabie Saoudite" (30/08/2026) : CALCULÉE sur classement réel FootyStats
#   (Saudi Pro League, saison 2025/26 complète -- 18 équipes, 34 matchs/
#   équipe, GF total = GA total = 921). Écart important avec l'ancienne
#   estimation devinée (1.20 -> 1.50) : cette ligue est nettement plus
#   offensive qu'estimé au départ.
# - "Corée du Sud" (30/08/2026) : CALCULÉE sur classement réel FootyStats
#   (K League 1, saison 2025 complète -- 12 équipes, 33 matchs/équipe, GF
#   total = GA total = 512, confirmé cohérent entre les deux colonnes).
#   Vérifiée par recoupement avec la saison 2026 en cours (151/198 matchs) :
#   1.21, du même ordre que 1.29 sur la saison complète -- retenue comme
#   plus fiable, valeur pas trop éloignée entre les deux saisons.
# - "Japon" (30/08/2026) : CALCULÉE sur classement réel FootyStats (J1
#   League, saison 2025 complète -- 20 équipes, 38 matchs/équipe, GF total
#   = GA total = 911).
# - "Estonie" (30/08/2026) : CALCULÉE (Meistriliiga, saison 2025 complète --
#   182/182 matchs, GF=GA=575).
# - "Tunisie" (30/08/2026) : CALCULÉE (Ligue 1, saison 2025/26 complète --
#   240/240 matchs, GF=GA=414).
# - "Etats-Unis" (30/08/2026) : CALCULÉE (MLS, saison 2025 complète --
#   540/540 matchs, 30 équipes, GF=GA=1629).
# - "South Africa" (30/08/2026) : CALCULÉE (Premier Soccer League, saison
#   2025/26 complète -- 240/240 matchs, GF=GA=485). Clé en anglais
#   volontairement -- c'est exactement le nom que matchendirect utilise
#   pour ce pays dans "competition" (vu dans le corpus), pas de traduction
#   française pour éviter de reproduire le bug Betpawa/ALIAS_PAYS trouvé
#   plus tôt dans l'autre sens.
# - "Chine" (30/08/2026) : CALCULÉE (Chinese Super League, saison 2025
#   complète -- 240/240 matchs, GF=GA=771).
# - "Écosse" : PAS ENCORE FAITE -- seule une saison 2026/27 à peine
#   commencée (16/198 matchs, 2-4 matchs/équipe) a été fournie, bien trop
#   courte pour être fiable (même problème que le Danemark au premier tour).
#   Retombe sur "default" en attendant une saison complète.
# Toute clé de pays absente retombe sur "default" (l'ancienne valeur 1.35,
# inchangée).
GA_REFERENCE = 1.35


def get_ga_reference(pays=None):
    """Référence défensive fixe du Module 2 v4.3.

    Le pays n'intervient pas dans le calcul : GA_REFERENCE est une constante
    externe unique, conformément à la règle N3bis de la base de référence.
    """
    return GA_REFERENCE


# Alias conservés uniquement pour compatibilité des entrées ; ils ne modifient
# plus la référence défensive fixe.
ALIAS_PAYS = {
    "Denmark": "Danemark", "Republic of Korea": "Corée du Sud", "South Korea": "Corée du Sud",
    "Bundesliga": "Allemagne", "Germany": "Allemagne", "Netherlands": "Pays-Bas",
    "Spain": "Espagne", "England": "Angleterre", "Italy": "Italie", "Belgium": "Belgique",
    "Turkey": "Turquie", "Greece": "Grèce", "Russia": "Russie", "Switzerland": "Suisse",
    "Poland": "Pologne", "Norway": "Norvège", "Sweden": "Suède", "Saudi Arabia": "Arabie Saoudite",
    "Japan": "Japon", "Estonie": "Estonia", "États-Unis": "Etats-Unis", "USA": "Etats-Unis",
    "United States": "Etats-Unis", "Afrique du Sud": "South Africa", "Chine": "China",
}


# Bornes défensives -- RÉGRESSION CORRIGÉE (04/09/2026 soir) : ce fichier
# avait été ramené à 0.70/1.30 (anciennes valeurs Module 2 v4.3), défaisant
# sans le documenter le correctif du 30/08 qui les avait élargies à 0.55/1.60
# suite à la saturation observée (41% des modificateurs de défense collés
# exactement sur l'ancienne borne). Régression confirmée accidentelle par
# Patrick -- remis à la valeur du 30/08.
BORNE_MIN_DEFENSE = 0.55
BORNE_MAX_DEFENSE = 1.60

# K_SHRINKAGE -- RÉGRESSION CORRIGÉE (04/09/2026 soir) : ce fichier avait
# K_SHRINKAGE=1.0 (aucune correction) ET ajuste_probabilite() qui renvoyait p
# inchangée -- la fonction existait mais n'était appelée nulle part dans le
# pipeline, donc le shrinkage n'avait AUCUN effet réel quelle que soit sa
# valeur. Régression confirmée accidentelle par Patrick.
#
# Valeur retenue (0.48) et seuil associé (0.02 ci-dessous) : PAS le calibrage
# théorique poolé (k=0.254, voir historique de session) -- ce dernier,
# combiné à FOURCHETTE_COTE_MAX=1.69, rend TOUT pari mathématiquement
# impossible (même p=1.0 après ce shrinkage ne peut jamais atteindre l'EV
# minimal à ces cotes -- vérifié par calcul, 0/125 candidats historiques
# passeraient). k=0.48/seuil=0.02 est le réglage qui maximise le taux de
# réussite réel sur les 63 paris (probabilité+cote réelle+résultat) qui
# existent concrètement dans historique_pronostics.json, sous contrainte
# d'un volume minimum (n=10) pour ne pas friser le pur bruit statistique :
# 70.0% de réussite réelle contre 57.1% avec l'ancien réglage (k=1.0).
#
# CE RÉGLAGE EST PROVISOIRE ET FRAGILE (n=10) -- pas un aboutissement.
# Le pipeline n'archivait jusqu'ici QUE les marchés qui passaient déjà le
# filtre EV, plafonnant les données exploitables pour ce calibrage à 63
# paris au total sur 9 jours. Le correctif d'archivage complet livré en
# même temps que ce fichier (voir run_pipeline.py, archive TOUS les
# marchés évalués avec leur cote réelle) doit faire grossir cet échantillon
# rapidement -- recalculer cette valeur dès que l'échantillon dépasse une
# quinzaine de paris par palier de k testé (voir calcule_roi.py, qui refait
# cette recherche de grille automatiquement chaque nuit).
K_SHRINKAGE = 0.48

def ajuste_probabilite(p):
    """Resserre la probabilité modèle vers 0.5 d'un facteur K_SHRINKAGE,
    pour corriger la surconfiance mesurée du modèle (voir historique de
    session -- écart constant d'environ 23 points entre le taux de
    réussite réel et la probabilité annoncée, sur deux échantillons
    indépendants). Appelée par calcule_ev() et kelly_stake() -- avant le
    04/09/2026, cette fonction existait mais n'était appelée nulle part,
    rendant K_SHRINKAGE totalement sans effet quelle que soit sa valeur."""
    return 0.5 + K_SHRINKAGE * (p - 0.5)


POIDS_FORME = 0.30
POIDS_CLASSEMENT = 0.20
POIDS_REPOS = 0.15
POIDS_ABSENCES = 0.15
POIDS_DISTANCE = 0.10
POIDS_H2H = 0.10
BORNE_RATIO = 0.15  # borne +/- par facteur avant pondération

RHO_DIXON_COLES = -0.1

# SEUIL_EV_MIN -- RÉGRESSION CORRIGÉE (04/09/2026 soir) : était retombé à
# 0.05 (ancienne valeur Module 3 v6.3). Valeur retenue ici (0.02) fait
# partie du même réglage empirique que K_SHRINKAGE ci-dessus (voir son
# commentaire) -- les deux ont été recherchés ensemble sur la grille
# (k, seuil_ev), pas indépendamment. Ne pas changer l'un sans l'autre sans
# refaire le calcul.
SEUIL_EV_MIN = 0.02
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
    for c in candidats_bruts:
        if c.get("cote_observee") is None:
            continue
        ev = calcule_ev(c["probabilite_modele"], c["cote_observee"])
        if ev is None or ev < seuil_ev:
            continue
        if not (cote_min <= c["cote_observee"] <= cote_max):
            continue
        liste_a.append({**c, "ev_brut": ev})
    return sorted(liste_a, key=lambda c: c["ev_brut"], reverse=True)


def construit_liste_b(liste_a, matrice, seuil_correlation=SEUIL_CORRELATION, nb_max=NB_PARIS_MAX):
    """
    Étape 4 Module 3 : filtre de corrélation mécanique. Parcourt LISTE_A
    (déjà triée par EV décroissant) et exclut tout candidat dont la
    corrélation avec un marché DÉJÀ retenu dépasse le seuil.
    """
    liste_b = []
    for candidat in liste_a:
        correle_a_un_retenu = any(
            abs(correlation_marches(matrice, candidat["condition"], retenu["condition"])) > seuil_correlation
            for retenu in liste_b
        )
        if not correle_a_un_retenu and len(liste_b) < nb_max:
            liste_b.append(candidat)
    return liste_b


def decision_go_nogo(liste_a, liste_b, nb_marches_evalues,
                      nb_matchs_domicile_utilises=None, nb_matchs_exterieur_utilises=None):
    """Étape 6 Module 3 v6.3 : GO si LISTE_B est non vide, sinon NO_GO.

    La confiance sur le nombre de matchs est descriptive uniquement (Étape 5bis)
    et ne constitue jamais un veto sur la décision.
    """
    if liste_b:
        return {"verdict_global": "GO", "motif_no_go": None}
    if liste_a:
        motif = f"{len(liste_a)} marché(s) dans la fourchette avec EV suffisant, tous exclus par corrélation"
    else:
        motif = (f"{nb_marches_evalues} marché(s) évalués, aucun dans la fourchette "
                 f"{FOURCHETTE_COTE_MIN}-{FOURCHETTE_COTE_MAX} avec EV>={SEUIL_EV_MIN*100:.0f}%")
    return {"verdict_global": "NO_GO", "motif_no_go": motif}


def confiance_lambda(nb_matchs_utilises: int) -> str:
    """Étape 5bis — indicateur descriptif, ne modifie aucun calcul."""
    if nb_matchs_utilises < CONFIANCE_LAMBDA_SEUILS["FAIBLE"]:
        return "FAIBLE"
    if nb_matchs_utilises < CONFIANCE_LAMBDA_SEUILS["MOYENNE"]:
        return "MOYENNE"
    return "NORMALE"


def calcule_lambda(gf_home_domicile, ga_home_domicile, gf_away_exterieur, ga_away_exterieur,
                    ratios_contextuels_home=None, ratios_contextuels_away=None, pays=None):
    """
    Règle N3 — reproduit Étapes 1 à 4 du Module 2 v4.3 à l'identique.
    ratios_contextuels_* : dict optionnel avec les clés parmi
        {"forme", "classement", "repos", "absences", "distance", "h2h"}
        chaque valeur déjà exprimée en ratio relatif à l'adversaire, non bornée.
    pays : (26/08/2026 -- calibration) nom du pays de la compétition, utilisé
        pour choisir la bonne valeur dans GA_REFERENCE_PAR_LIGUE. None ->
        valeur "default" (comportement identique à l'ancien GA_REFERENCE fixe).
    """
    ga_reference = get_ga_reference(pays)
    poids = {
        "forme": POIDS_FORME, "classement": POIDS_CLASSEMENT, "repos": POIDS_REPOS,
        "absences": POIDS_ABSENCES, "distance": POIDS_DISTANCE, "h2h": POIDS_H2H,
    }

    def ajustement(ratios):
        if not ratios:
            return 0.0
        num, den = 0.0, 0.0
        for cle, valeur in ratios.items():
            if cle not in poids:
                continue
            r = clamp(valeur, -BORNE_RATIO, BORNE_RATIO)
            num += poids[cle] * r
            den += poids[cle]
        return num / den if den > 0 else 0.0

    lambda_home_base = gf_home_domicile
    lambda_away_base = gf_away_exterieur

    modifier_defense_away = clamp(ga_away_exterieur / ga_reference, BORNE_MIN_DEFENSE, BORNE_MAX_DEFENSE)
    modifier_defense_home = clamp(ga_home_domicile / ga_reference, BORNE_MIN_DEFENSE, BORNE_MAX_DEFENSE)

    lambda_home_prelim = lambda_home_base * modifier_defense_away
    lambda_away_prelim = lambda_away_base * modifier_defense_home

    ajustement_home = ajustement(ratios_contextuels_home)
    ajustement_away = ajustement(ratios_contextuels_away)

    lambda_home = lambda_home_prelim * math.exp(ajustement_home)
    lambda_away = lambda_away_prelim * math.exp(ajustement_away)

    return {
        "lambda_home": lambda_home,
        "lambda_away": lambda_away,
        "audit": {
            "lambda_home_base": lambda_home_base,
            "lambda_away_base": lambda_away_base,
            "modifier_defense_home": modifier_defense_home,
            "modifier_defense_away": modifier_defense_away,
            "ajustement_home": ajustement_home,
            "ajustement_away": ajustement_away,
        },
    }


def _tau_dixon_coles(x, y, lambda_home, lambda_away, rho=RHO_DIXON_COLES):
    """Correction Dixon-Coles standard sur les 4 cases de score bas."""
    if x == 0 and y == 0:
        return 1 - lambda_home * lambda_away * rho
    if x == 0 and y == 1:
        return 1 + lambda_home * rho
    if x == 1 and y == 0:
        return 1 + lambda_away * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


def matrice_poisson_dixon_coles(lambda_home, lambda_away, max_buts=5):
    """Règle N6 — tableau P(k,j) pour k,j de 0 à max_buts, agrégé en '5+' au-delà."""

    def poisson_pmf(k, lam):
        return (lam ** k) * math.exp(-lam) / math.factorial(k)

    matrice = {}
    for x in range(max_buts + 1):
        for y in range(max_buts + 1):
            p = poisson_pmf(x, lambda_home) * poisson_pmf(y, lambda_away)
            p *= _tau_dixon_coles(x, y, lambda_home, lambda_away)
            matrice[(x, y)] = max(p, 0.0)

    total = sum(matrice.values())
    if total > 0:
        matrice = {k: v / total for k, v in matrice.items()}
    return matrice


def probabilite_marche(matrice, condition):
    """condition: fonction(x, y) -> bool. Somme les cases correspondantes."""
    return sum(p for (x, y), p in matrice.items() if condition(x, y))


def probabilite_double_chance(matrice):
    p1 = probabilite_marche(matrice, lambda x, y: x > y)
    pn = probabilite_marche(matrice, lambda x, y: x == y)
    p2 = probabilite_marche(matrice, lambda x, y: x < y)
    return {"1X": p1 + pn, "12": p1 + p2, "X2": pn + p2}


def probabilite_over_under(matrice, ligne, equipe=None):
    """
    equipe=None -> total buts du match. equipe='home'/'away' -> buts d'une
    seule équipe. ligne peut être un demi-entier (0.5, 1.5, 2.5...) ou un
    entier (traité comme ligne asiatique simple, sans push géré ici).
    """
    if equipe == "home":
        cond_total = lambda x, y: x
    elif equipe == "away":
        cond_total = lambda x, y: y
    else:
        cond_total = lambda x, y: x + y

    plus = sum(p for (x, y), p in matrice.items() if cond_total(x, y) > ligne)
    moins = sum(p for (x, y), p in matrice.items() if cond_total(x, y) < ligne)
    egal = sum(p for (x, y), p in matrice.items() if cond_total(x, y) == ligne)
    return {"plus": plus, "moins": moins, "push": egal}


def probabilite_btts(matrice):
    oui = sum(p for (x, y), p in matrice.items() if x > 0 and y > 0)
    return {"oui": oui, "non": 1 - oui}


def probabilite_handicap_2choix(matrice, ligne_domicile):
    """
    ligne_domicile : handicap appliqué à l'équipe à domicile, ex: -1.5 signifie
    "domicile doit gagner par 2 buts d'écart ou plus pour couvrir".
    Lignes demi-entières uniquement (pas de push possible).
    """
    if ligne_domicile == int(ligne_domicile):
        raise ValueError("probabilite_handicap_2choix ne gère que les lignes demi-entières (pas de push). "
                          "Pour les lignes entières, saisie manuelle requise (Handicap à 3 choix).")
    domicile_couvre = sum(
        p for (x, y), p in matrice.items() if (x + ligne_domicile) > y
    )
    return {"domicile": domicile_couvre, "exterieur": 1 - domicile_couvre}


def probabilite_score_exact(matrice, x, y):
    return matrice.get((x, y), 0.0)


def probabilite_nombre_exact_buts(matrice, n):
    """Probabilité que le total de buts soit EXACTEMENT n (pas un cumul)."""
    return sum(p for (bx, by), p in matrice.items() if bx + by == n)


def probabilite_nombre_buts_ou_plus(matrice, n):
    """Probabilité que le total de buts soit >= n. Sert uniquement pour la
    queue de distribution (ex: '6+'), jamais pour une valeur isolée."""
    return sum(p for (bx, by), p in matrice.items() if bx + by >= n)


def probabilite_pair_impair(matrice):
    pair = sum(p for (x, y), p in matrice.items() if (x + y) % 2 == 0)
    return {"pair": pair, "impair": 1 - pair}


def probabilite_cages_inviolees(matrice, equipe):
    """P(l'adversaire de `equipe` ne marque pas) — 'clean sheet' pour `equipe`."""
    if equipe == "home":
        oui = sum(p for (x, y), p in matrice.items() if y == 0)
    else:
        oui = sum(p for (x, y), p in matrice.items() if x == 0)
    return {"oui": oui, "non": 1 - oui}


def construit_probabilites_marches(matrice, lignes_ou=(0.5, 1.5, 2.5, 3.5, 4.5),
                                    lignes_handicap=(-2.5, -1.5, -0.5, 0.5, 1.5, 2.5)):
    """
    Construit le dictionnaire complet des probabilités modèle pour tous les
    marchés v1 (buts uniquement). Clés stables, consommées telles quelles par
    le frontend (script.js).
    """
    marches = {
        "1x2": {
            "1": probabilite_marche(matrice, lambda x, y: x > y),
            "X": probabilite_marche(matrice, lambda x, y: x == y),
            "2": probabilite_marche(matrice, lambda x, y: x < y),
        },
        "double_chance": probabilite_double_chance(matrice),
        "btts": probabilite_btts(matrice),
        "pair_impair": probabilite_pair_impair(matrice),
        "cages_inviolees_domicile": probabilite_cages_inviolees(matrice, "home"),
        "cages_inviolees_exterieur": probabilite_cages_inviolees(matrice, "away"),
        "over_under": {},
        "over_under_domicile": {},
        "over_under_exterieur": {},
        "handicap": {},
        "score_exact": {},
        "nombre_exact_buts": {},
    }

    for ligne in lignes_ou:
        marches["over_under"][str(ligne)] = probabilite_over_under(matrice, ligne)
        marches["over_under_domicile"][str(ligne)] = probabilite_over_under(matrice, ligne, "home")
        marches["over_under_exterieur"][str(ligne)] = probabilite_over_under(matrice, ligne, "away")

    for ligne in lignes_handicap:
        marches["handicap"][str(ligne)] = probabilite_handicap_2choix(matrice, ligne)

    for x in range(6):
        for y in range(6):
            marches["score_exact"][f"{x}-{y}"] = probabilite_score_exact(matrice, x, y)

    for n in range(6):
        marches["nombre_exact_buts"][str(n)] = probabilite_nombre_exact_buts(matrice, n)
    marches["nombre_exact_buts"]["6+"] = probabilite_nombre_buts_ou_plus(matrice, 6)

    return marches


def calcule_ev(probabilite_modele, cote_observee):
    """Règle N8 — EV = (cote x probabilité modèle AJUSTÉE) - 1.

    CORRECTIF (04/09/2026 soir) : applique désormais ajuste_probabilite()
    en interne avant le calcul. Avant ce correctif, cette fonction utilisait
    la probabilité brute du modèle -- ajuste_probabilite() existait dans ce
    même fichier mais n'était appelée nulle part, rendant K_SHRINKAGE sans
    aucun effet réel. probabilite_modele reçu ici reste la valeur BRUTE
    (celle affichée telle quelle ailleurs, ex. LISTE_A/LISTE_B) -- c'est ce
    point d'entrée qui resserre, pas l'appelant.
    """
    if cote_observee is None:
        return None
    return (cote_observee * ajuste_probabilite(probabilite_modele)) - 1


def kelly_stake(probabilite_modele, cote_observee):
    """Étape 7 Module 3 v6.3 — Kelly fractionné à 25%, plafond 4%.

    CORRECTIF (04/09/2026 soir) : la probabilité utilisée pour la mise
    Kelly elle-même est maintenant celle resserrée par ajuste_probabilite()
    -- avant ce correctif, le commentaire ici affirmait explicitement
    l'inverse ("exactement celle du modèle, sans shrinkage"), ce qui était
    de toute façon cohérent avec le reste du fichier à l'époque (shrinkage
    non branché), mais aurait été une incohérence dangereuse si seul
    calcule_ev() avait été corrigé sans toucher ce calcul : le filtre EV
    aurait jugé le pari sur la probabilité honnête, puis la mise aurait été
    dimensionnée sur la probabilité brute surconfiante -- sur-mise
    systématique par rapport à l'edge réel.
    """
    if cote_observee is None:
        return 0.0
    ev = calcule_ev(probabilite_modele, cote_observee)
    if ev is None or ev < SEUIL_EV_MIN:
        return 0.0
    if not (FOURCHETTE_COTE_MIN <= cote_observee <= FOURCHETTE_COTE_MAX):
        return 0.0

    p_adj = ajuste_probabilite(probabilite_modele)
    b = cote_observee - 1
    q = 1 - p_adj
    f_kelly = (b * p_adj - q) / b if b > 0 else 0.0
    if f_kelly <= 0:
        return 0.0

    mise = f_kelly * KELLY_FRACTION
    return min(mise, MISE_MAX_PARI)


def est_standout(probabilite_modele, cote_observee):
    """
    Critère 'Pari en or' (Module 4) — EV >= SEUIL_STANDOUT.
    CORRECTIF (25/08) : doit aussi respecter la fourchette de cote
    exploitable (FOURCHETTE_COTE_MIN/MAX), comme kelly_stake(). Avant ce
    correctif, un match avec un fort EV mais une cote hors fourchette
    (ex. 3.80, un outsider) était marqué "standout" alors qu'aucune mise
    n'est jamais recommandée dessus (mise_kelly = 0) — badge trompeur sur
    le site, découvert dès que cote_1 a commencé à circuler réellement.
    """
    if cote_observee is None:
        return False
    if not (FOURCHETTE_COTE_MIN <= cote_observee <= FOURCHETTE_COTE_MAX):
        return False
    ev = calcule_ev(probabilite_modele, cote_observee)
    return ev is not None and ev >= SEUIL_STANDOUT


def plafonner_cluster(paris, plafond_cluster=CLUSTER_MAX, nb_max=NB_PARIS_MAX):
    """
    Filtre simple : garde au plus NB_PARIS_MAX paris (les plus forts EV en premier),
    et plafonne la somme des mises à plafond_cluster.
    """
    paris_tries = sorted(paris, key=lambda p: p.get("ev", 0), reverse=True)[:nb_max]
    total = sum(p.get("mise", 0) for p in paris_tries)
    if total > plafond_cluster and total > 0:
        facteur = plafond_cluster / total
        for p in paris_tries:
            p["mise"] = p["mise"] * facteur
    return paris_tries
