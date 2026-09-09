"""
archetype_model/signals/deduplication.py — Dédoublonnage (ARCHETYPE_FOOT
v3, §12.2, CORRECTIF 9) :

    "Un seul candidat retenu par famille ET par groupe d'exposition --
    règle déterministe, jamais un comptage de signaux."

Cascade de critères pour départager les candidats à l'intérieur d'un
même groupe (famille, puis groupe d'exposition) :
    1. Robustesse (STABLE avant INSTABLE) ;
    2. Palier de fiabilité H2H le plus élevé (TRES_FIABLE > FIABLE >
       INDICATIF > INSUFFISANT) ;
    3. Edge ou EDV selon le rôle visé (P1→Edge, P2→EDV), décroissant.

La cascade s'ARRÊTE au premier critère qui différencie -- jamais une
addition ou une pondération des trois (ce serait recréer le score
caché explicitement interdit par le CORRECTIF 9).

DEUX CONTRAINTES, PAS UNE (point vérifié dans le texte du v3 avant de
coder, 09/09/2026) : "par famille ET par groupe d'exposition" sont
deux regroupements séparés, pas une seule clé (famille, groupe). Deux
familles différentes peuvent partager le même groupe d'exposition
(économiquement corrélées) -- réduire uniquement par (famille, groupe)
combinés laisserait passer deux candidats de familles différentes mais
du même groupe, ce qui violerait la contrainte "un seul par groupe".
Ce module réduit donc en DEUX ÉTAPES : d'abord un candidat par
famille, puis, parmi ces représentants de famille, un candidat par
groupe d'exposition.

H2H UTILISÉ ICI COMME DÉPARTAGE UNIQUEMENT (décision du 09/09/2026) :
le palier de fiabilité H2H influence QUI représente sa famille/groupe,
mais n'élimine jamais un candidat à lui seul -- H2H reste non
décisionnel jusqu'à la sélection finale P1/P2/P3 (arbitrage), où son
statut CORROBORE/CONTREDIT devient un vrai critère d'exclusion (non
codé ici, chantier séparé).

ROBUSTESSE : le critère 1 de la cascade est un NO-OP EN PRATIQUE ici,
et c'est assumé, pas une négligence -- `signals.convergence` (le
filtre en amont) n'accepte déjà que des candidats STABLE (INSTABLE est
éliminé avant d'arriver ici). Le critère est gardé pour rester fidèle
à la cascade du v3 telle qu'écrite, et pour rester correct si jamais
un appelant futur lui passait des candidats non filtrés.

STRUCTURE D'ENTRÉE ATTENDUE : ce module ne connaît pas le référentiel
central (§9.1, non codé) -- chaque candidat DOIT déjà porter ses
propres "market_family"/"exposure_group"/"h2h_palier"/"robustesse"/
"edge"/"edv", assignés par l'appelant. Aucune classification n'est
faite ici.
"""

ORDRE_ROBUSTESSE = {"STABLE": 1, "INSTABLE": 0}
ORDRE_PALIER_H2H = {"TRES_FIABLE": 3, "FIABLE": 2, "INDICATIF": 1, "INSUFFISANT": 0}

CRITERES_VALIDES = ("edge", "edv")


def _cle_tri(candidat, critere):
    """Clé de comparaison pour la cascade -- robustesse, puis palier
    H2H, puis le critère (edge/edv) décroissant. Valeurs absentes ou
    inconnues traitées comme le rang le plus bas (jamais une
    exception), pour ne jamais faire planter tout le dédoublonnage à
    cause d'un candidat mal formé."""
    valeur_critere = candidat.get(critere)
    return (
        ORDRE_ROBUSTESSE.get(candidat.get("robustesse"), 0),
        ORDRE_PALIER_H2H.get(candidat.get("h2h_palier"), 0),
        valeur_critere if valeur_critere is not None else float("-inf"),
    )


def _meilleur(candidats, critere):
    return max(candidats, key=lambda c: _cle_tri(c, critere))


def deduplique(candidats, critere="edge"):
    """
    Réduit `candidats` (tous supposés déjà ÉLIGIBLES -- ce module ne
    revérifie pas l'éligibilité, voir signals.convergence pour ça) à
    au plus UN candidat par `market_family`, ET au plus UN par
    `exposure_group`, simultanément.

    `critere` : "edge" (contexte P1) ou "edv" (contexte P2) -- lève
    une ValueError si autre chose (v3 §12.2 : "selon le rôle visé",
    jamais un troisième choix implicite).

    Retourne la liste des candidats retenus (dicts, inchangés --
    aucune donnée n'est recalculée ou modifiée ici), dans un ordre non
    garanti (le dédoublonnage ne trie pas le résultat final, seulement
    à l'intérieur de chaque groupe pour départager).
    """
    if critere not in CRITERES_VALIDES:
        raise ValueError(f"critere invalide : {critere!r}, attendu un de {CRITERES_VALIDES}")

    # Étape 1 : un seul candidat par famille.
    par_famille = {}
    for c in candidats:
        par_famille.setdefault(c["market_family"], []).append(c)
    representants_famille = [_meilleur(membres, critere) for membres in par_famille.values()]

    # Étape 2 : parmi les représentants de famille, un seul par groupe
    # d'exposition -- nécessaire car deux familles peuvent partager un
    # groupe (voir docstring de module).
    par_groupe = {}
    for c in representants_famille:
        par_groupe.setdefault(c["exposure_group"], []).append(c)
    representants_finaux = [_meilleur(membres, critere) for membres in par_groupe.values()]

    return representants_finaux
