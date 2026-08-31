"""
calculs.py â€” Portage dÃ©terministe des RÃ¨gles N3 / N4 / N6 / N7 (Module 2 v4.3)
et de l'Ã‰tape 7 (Module 3 v6.3), UNIQUEMENT la partie mathÃ©matique fixe.

Ce fichier N'IMPLÃ‰MENTE PAS :
- la vÃ©rification de fraÃ®cheur des pages sources (Module 1)
- la dÃ©tection de pÃ©nalitÃ©s de points (Module 1)
- le risque de rotation continentale (Module 1 v1.7)
- la double vÃ©rification des handicaps 3 voies (Module 3, Ã‰tape 4)
- toute analyse de corrÃ©lation sÃ©mantique entre marchÃ©s (nÃ©cessite jugement,
  pas juste un chiffre â€” cf. SEUIL_CORRELATION ci-dessous, implÃ©mentÃ© seulement
  pour le cas simple "mÃªme match, marchÃ©s mÃ©caniquement liÃ©s")

Ces points restent des tÃ¢ches manuelles ou une v2 â€” les inclure de faÃ§on fiable
avant demain reviendrait Ã  rÃ©Ã©crire en code un jugement d'agent, pas juste une formule.

Constantes reprises telles quelles de TABLEAU_RECAPITULATIF.md (gelÃ©es jusqu'Ã 
backtest historique â€” ne pas modifier sans repasser par ce document).
"""

import math

# --- Constantes gelÃ©es (Module 2 / Module 3) ---
# GA_REFERENCE : constante externe fixe du Module 2 v4.3.
# - "NorvÃ¨ge"/"SuÃ¨de"/"Danemark" (29/08/2026), "Italie"/"Allemagne"/
#   "France"/"Turquie"/"Espagne"/"Angleterre"/"Pays-Bas"/"Portugal"/"GrÃ¨ce"/
#   "Belgique"/"Russie"/"Suisse"/"Pologne" (30/08/2026) : CALCULÃ‰ES sur
#   donnÃ©es rÃ©elles (Football-Data.co.uk). Saison retenue par pays -- la
#   PLUS RÃ‰CENTE COMPLÃˆTE, jamais une saison en cours trop courte (le
#   Danemark 2026/2027 n'avait que 28 matchs, Ã©cart de 0.25 avec sa saison
#   complÃ¨te -- mÃªme logique appliquÃ©e Ã  Russie/Suisse/Pologne ci-dessous,
#   dont la saison 2026/2027 n'avait que 16 Ã  38 matchs) :
#     Italie 2025/2026 (380 matchs), Allemagne 2025/2026 (306), France
#     2025/2026 (306), Turquie 2025/2026 (306), Espagne 2025/2026 (380),
#     Angleterre 2025/2026 (380), Pays-Bas 2025/2026 (306), Portugal
#     2025/2026 (306), GrÃ¨ce 2025/2026 (236), Belgique 2025/2026 (311),
#     NorvÃ¨ge 2025 (240), SuÃ¨de 2025 (240), Danemark 2025/2026 (192),
#     Russie 2025/2026 (240), Suisse 2025/2026 (228), Pologne 2025/2026 (306).
# - "Arabie Saoudite" (30/08/2026) : CALCULÃ‰E sur classement rÃ©el FootyStats
#   (Saudi Pro League, saison 2025/26 complÃ¨te -- 18 Ã©quipes, 34 matchs/
#   Ã©quipe, GF total = GA total = 921). Ã‰cart important avec l'ancienne
#   estimation devinÃ©e (1.20 -> 1.50) : cette ligue est nettement plus
#   offensive qu'estimÃ© au dÃ©part.
# - "CorÃ©e du Sud" (30/08/2026) : CALCULÃ‰E sur classement rÃ©el FootyStats
#   (K League 1, saison 2025 complÃ¨te -- 12 Ã©quipes, 33 matchs/Ã©quipe, GF
#   total = GA total = 512, confirmÃ© cohÃ©rent entre les deux colonnes).
#   VÃ©rifiÃ©e par recoupement avec la saison 2026 en cours (151/198 matchs) :
#   1.21, du mÃªme ordre que 1.29 sur la saison complÃ¨te -- retenue comme
#   plus fiable, valeur pas trop Ã©loignÃ©e entre les deux saisons.
# - "Japon" (30/08/2026) : CALCULÃ‰E sur classement rÃ©el FootyStats (J1
#   League, saison 2025 complÃ¨te -- 20 Ã©quipes, 38 matchs/Ã©quipe, GF total
#   = GA total = 911).
# - "Estonie" (30/08/2026) : CALCULÃ‰E (Meistriliiga, saison 2025 complÃ¨te --
#   182/182 matchs, GF=GA=575).
# - "Tunisie" (30/08/2026) : CALCULÃ‰E (Ligue 1, saison 2025/26 complÃ¨te --
#   240/240 matchs, GF=GA=414).
# - "Etats-Unis" (30/08/2026) : CALCULÃ‰E (MLS, saison 2025 complÃ¨te --
#   540/540 matchs, 30 Ã©quipes, GF=GA=1629).
# - "South Africa" (30/08/2026) : CALCULÃ‰E (Premier Soccer League, saison
#   2025/26 complÃ¨te -- 240/240 matchs, GF=GA=485). ClÃ© en anglais
#   volontairement -- c'est exactement le nom que matchendirect utilise
#   pour ce pays dans "competition" (vu dans le corpus), pas de traduction
#   franÃ§aise pour Ã©viter de reproduire le bug Betpawa/ALIAS_PAYS trouvÃ©
#   plus tÃ´t dans l'autre sens.
# - "Chine" (30/08/2026) : CALCULÃ‰E (Chinese Super League, saison 2025
#   complÃ¨te -- 240/240 matchs, GF=GA=771).
# - "Ã‰cosse" : PAS ENCORE FAITE -- seule une saison 2026/27 Ã  peine
#   commencÃ©e (16/198 matchs, 2-4 matchs/Ã©quipe) a Ã©tÃ© fournie, bien trop
#   courte pour Ãªtre fiable (mÃªme problÃ¨me que le Danemark au premier tour).
#   Retombe sur "default" en attendant une saison complÃ¨te.
# Toute clÃ© de pays absente retombe sur "default" (l'ancienne valeur 1.35,
# inchangÃ©e).
GA_REFERENCE = 1.35


def get_ga_reference(pays=None):
    """RÃ©fÃ©rence dÃ©fensive fixe du Module 2 v4.3.

    Le pays n'intervient pas dans le calcul : GA_REFERENCE est une constante
    externe unique, conformÃ©ment Ã  la rÃ¨gle N3bis de la base de rÃ©fÃ©rence.
    """
    return GA_REFERENCE


# Alias conservÃ©s uniquement pour compatibilitÃ© des entrÃ©es ; ils ne modifient
# plus la rÃ©fÃ©rence dÃ©fensive fixe.
ALIAS_PAYS = {
    "Denmark": "Danemark", "Republic of Korea": "CorÃ©e du Sud", "South Korea": "CorÃ©e du Sud",
    "Bundesliga": "Allemagne", "Germany": "Allemagne", "Netherlands": "Pays-Bas",
    "Spain": "Espagne", "England": "Angleterre", "Italy": "Italie", "Belgium": "Belgique",
    "Turkey": "Turquie", "Greece": "GrÃ¨ce", "Russia": "Russie", "Switzerland": "Suisse",
    "Poland": "Pologne", "Norway": "NorvÃ¨ge", "Sweden": "SuÃ¨de", "Saudi Arabia": "Arabie Saoudite",
    "Japan": "Japon", "Estonie": "Estonia", "Ã‰tats-Unis": "Etats-Unis", "USA": "Etats-Unis",
    "United States": "Etats-Unis", "Afrique du Sud": "South Africa", "Chine": "China",
}


# Bornes dÃ©fensives exactes du Module 2 v4.3.
BORNE_MIN_DEFENSE = 0.70
BORNE_MAX_DEFENSE = 1.30

# Aucun shrinkage probabiliste : la base v4.3 interdit toute modification
# silencieuse de la probabilitÃ© modÃ¨le aprÃ¨s Poisson/Dixon-Coles.
K_SHRINKAGE = 1.0

def ajuste_probabilite(p):
    """CompatibilitÃ© API : retourne la probabilitÃ© modÃ¨le inchangÃ©e."""
    return p


POIDS_FORME = 0.30
POIDS_CLASSEMENT = 0.20
POIDS_REPOS = 0.15
POIDS_ABSENCES = 0.15
POIDS_DISTANCE = 0.10
POIDS_H2H = 0.10
BORNE_RATIO = 0.15  # borne +/- par facteur avant pondÃ©ration

RHO_DIXON_COLES = -0.1

# Seuil EV exact du Module 3 v6.3.
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
# Ã‰tape 3 (Module 2 v4.3) â€” ratios contextuels. Forme, Absences, Distance
# ANNULÃ‰S sur dÃ©cision explicite (25/08) : Forme jamais formalisÃ©e sur ce
# projet, Absences non fiable Ã  scraper sur matchendirect (pas de liste
# blessÃ©s/suspendus confirmÃ©e), Distance jamais commencÃ©e (gÃ©ocodage).
# Seuls Classement et H2H sont calculÃ©s. Le garde-fou "donnÃ©e absente ->
# ratio neutre (0.0)" du Module 2 s'applique aux deux -- jamais une erreur,
# jamais une estimation devinÃ©e.
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
    `classement` : liste renvoyÃ©e par recupere_classement_du_match
    (scraper_details.py), dÃ©jÃ  triÃ©e par rang (ordre du document = ordre
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
    sur les 10 derniÃ¨res confrontations directes disponibles (ou moins si
    l'historique est plus court). `historique_h2h` : sortie de
    recupere_h2h (scraper_details.py), plus rÃ©cent en premier.
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
# Module 3 v6.3 â€” Ã‰tapes 1, 2, 4, 6 (25/08). Handicap 3 voies (Ã‰tape 0) EXCLU
# sur dÃ©cision explicite. Rotation continentale EXCLUE. Le dimensionnement
# Kelly (Ã‰tape 7, dÃ©jÃ  existant ci-dessus) reste strictement inchangÃ©.
# --------------------------------------------------------------------------

def correlation_marches(matrice, condition_a, condition_b):
    """
    CorrÃ©lation de Pearson EXACTE entre deux indicatrices de marchÃ©, calculÃ©e
    sur la matrice jointe Poisson/Dixon-Coles dÃ©jÃ  produite pour le match --
    un calcul mÃ©canique dÃ©terminÃ© par le modÃ¨le lui-mÃªme, pas une estimation
    ni un jugement sÃ©mantique. Sert Ã  Ã©viter d'empiler des mises sur des
    marchÃ©s redondants du MÃŠME match (Ã‰tape 4, Module 3 v6.3).
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
    Ã‰tapes 1-2 Module 3 : plancher EV (5%) puis fourchette de cote
    (1.25-1.69). `candidats_bruts` : liste de dicts
    {"marche", "condition" (fn(x,y)->bool), "probabilite_modele", "cote_observee"}.
    Retourne LISTE_A, triÃ©e par EV dÃ©croissant. Un candidat sans cote
    (cote_observee=None) est Ã©cartÃ© silencieusement, jamais une erreur.
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
    Ã‰tape 4 Module 3 : filtre de corrÃ©lation mÃ©canique. Parcourt LISTE_A
    (dÃ©jÃ  triÃ©e par EV dÃ©croissant) et exclut tout candidat dont la
    corrÃ©lation avec un marchÃ© DÃ‰JÃ€ retenu dÃ©passe le seuil.
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
    """Ã‰tape 6 Module 3 v6.3 : GO si LISTE_B est non vide, sinon NO_GO.

    La confiance sur le nombre de matchs est descriptive uniquement (Ã‰tape 5bis)
    et ne constitue jamais un veto sur la dÃ©cision.
    """
    if liste_b:
        return {"verdict_global": "GO", "motif_no_go": None}
    if liste_a:
        motif = f"{len(liste_a)} marchÃ©(s) dans la fourchette avec EV suffisant, tous exclus par corrÃ©lation"
    else:
        motif = (f"{nb_marches_evalues} marchÃ©(s) Ã©valuÃ©s, aucun dans la fourchette "
                 f"{FOURCHETTE_COTE_MIN}-{FOURCHETTE_COTE_MAX} avec EV>={SEUIL_EV_MIN*100:.0f}%")
    return {"verdict_global": "NO_GO", "motif_no_go": motif}


def confiance_lambda(nb_matchs_utilises: int) -> str:
    """Ã‰tape 5bis â€” indicateur descriptif, ne modifie aucun calcul."""
    if nb_matchs_utilises < CONFIANCE_LAMBDA_SEUILS["FAIBLE"]:
        return "FAIBLE"
    if nb_matchs_utilises < CONFIANCE_LAMBDA_SEUILS["MOYENNE"]:
        return "MOYENNE"
    return "NORMALE"


def calcule_lambda(gf_home_domicile, ga_home_domicile, gf_away_exterieur, ga_away_exterieur,
                    ratios_contextuels_home=None, ratios_contextuels_away=None, pays=None):
    """
    RÃ¨gle N3 â€” reproduit Ã‰tapes 1 Ã  4 du Module 2 v4.3 Ã  l'identique.
    ratios_contextuels_* : dict optionnel avec les clÃ©s parmi
        {"forme", "classement", "repos", "absences", "distance", "h2h"}
        chaque valeur dÃ©jÃ  exprimÃ©e en ratio relatif Ã  l'adversaire, non bornÃ©e.
    pays : (26/08/2026 -- calibration) nom du pays de la compÃ©tition, utilisÃ©
        pour choisir la bonne valeur dans GA_REFERENCE_PAR_LIGUE. None ->
        valeur "default" (comportement identique Ã  l'ancien GA_REFERENCE fixe).
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
    """RÃ¨gle N6 â€” tableau P(k,j) pour k,j de 0 Ã  max_buts, agrÃ©gÃ© en '5+' au-delÃ ."""

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
    seule Ã©quipe. ligne peut Ãªtre un demi-entier (0.5, 1.5, 2.5...) ou un
    entier (traitÃ© comme ligne asiatique simple, sans push gÃ©rÃ© ici).
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
    ligne_domicile : handicap appliquÃ© Ã  l'Ã©quipe Ã  domicile, ex: -1.5 signifie
    "domicile doit gagner par 2 buts d'Ã©cart ou plus pour couvrir".
    Lignes demi-entiÃ¨res uniquement (pas de push possible).
    """
    if ligne_domicile == int(ligne_domicile):
        raise ValueError("probabilite_handicap_2choix ne gÃ¨re que les lignes demi-entiÃ¨res (pas de push). "
                          "Pour les lignes entiÃ¨res, saisie manuelle requise (Handicap Ã  3 choix).")
    domicile_couvre = sum(
        p for (x, y), p in matrice.items() if (x + ligne_domicile) > y
    )
    return {"domicile": domicile_couvre, "exterieur": 1 - domicile_couvre}


def probabilite_score_exact(matrice, x, y):
    return matrice.get((x, y), 0.0)


def probabilite_nombre_exact_buts(matrice, n):
    """ProbabilitÃ© que le total de buts soit EXACTEMENT n (pas un cumul)."""
    return sum(p for (bx, by), p in matrice.items() if bx + by == n)


def probabilite_nombre_buts_ou_plus(matrice, n):
    """ProbabilitÃ© que le total de buts soit >= n. Sert uniquement pour la
    queue de distribution (ex: '6+'), jamais pour une valeur isolÃ©e."""
    return sum(p for (bx, by), p in matrice.items() if bx + by >= n)


def probabilite_pair_impair(matrice):
    pair = sum(p for (x, y), p in matrice.items() if (x + y) % 2 == 0)
    return {"pair": pair, "impair": 1 - pair}


def probabilite_cages_inviolees(matrice, equipe):
    """P(l'adversaire de `equipe` ne marque pas) â€” 'clean sheet' pour `equipe`."""
    if equipe == "home":
        oui = sum(p for (x, y), p in matrice.items() if y == 0)
    else:
        oui = sum(p for (x, y), p in matrice.items() if x == 0)
    return {"oui": oui, "non": 1 - oui}


def construit_probabilites_marches(matrice, lignes_ou=(0.5, 1.5, 2.5, 3.5, 4.5),
                                    lignes_handicap=(-2.5, -1.5, -0.5, 0.5, 1.5, 2.5)):
    """
    Construit le dictionnaire complet des probabilitÃ©s modÃ¨le pour tous les
    marchÃ©s v1 (buts uniquement). ClÃ©s stables, consommÃ©es telles quelles par
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
    """RÃ¨gle N8 â€” EV = (cote x probabilitÃ© modÃ¨le) - 1."""
    if cote_observee is None:
        return None
    return (cote_observee * probabilite_modele) - 1


def kelly_stake(probabilite_modele, cote_observee):
    """Ã‰tape 7 Module 3 v6.3 â€” Kelly fractionnÃ© Ã  25%, plafond 4%.

    La probabilitÃ© utilisÃ©e est exactement celle du modÃ¨le, sans shrinkage.
    """
    if cote_observee is None:
        return 0.0
    ev = calcule_ev(probabilite_modele, cote_observee)
    if ev is None or ev < SEUIL_EV_MIN:
        return 0.0
    if not (FOURCHETTE_COTE_MIN <= cote_observee <= FOURCHETTE_COTE_MAX):
        return 0.0

    b = cote_observee - 1
    q = 1 - probabilite_modele
    f_kelly = (b * probabilite_modele - q) / b if b > 0 else 0.0
    if f_kelly <= 0:
        return 0.0

    mise = f_kelly * KELLY_FRACTION
    return min(mise, MISE_MAX_PARI)


def est_standout(probabilite_modele, cote_observee):
    """
    CritÃ¨re 'Pari en or' (Module 4) â€” EV >= SEUIL_STANDOUT.
    CORRECTIF (25/08) : doit aussi respecter la fourchette de cote
    exploitable (FOURCHETTE_COTE_MIN/MAX), comme kelly_stake(). Avant ce
    correctif, un match avec un fort EV mais une cote hors fourchette
    (ex. 3.80, un outsider) Ã©tait marquÃ© "standout" alors qu'aucune mise
    n'est jamais recommandÃ©e dessus (mise_kelly = 0) â€” badge trompeur sur
    le site, dÃ©couvert dÃ¨s que cote_1 a commencÃ© Ã  circuler rÃ©ellement.
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
    et plafonne la somme des mises Ã  plafond_cluster.
    """
    paris_tries = sorted(paris, key=lambda p: p.get("ev", 0), reverse=True)[:nb_max]
    total = sum(p.get("mise", 0) for p in paris_tries)
    if total > plafond_cluster and total > 0:
        facteur = plafond_cluster / total
        for p in paris_tries:
            p["mise"] = p["mise"] * facteur
    return paris_tries
