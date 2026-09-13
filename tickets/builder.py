"""
tickets/builder.py — Construction de tickets avec contrôle de dépendance.

Pourquoi ce module existe : combiner des pronostics dans un ticket
suppose que leur produit de probabilités reflète la vraie chance de
succès du ticket -- vrai seulement si les jambes sont indépendantes.
Répond à la Question 10 (adressée au bureau d'étude le 13/09/2026,
tranchée par eux le même jour) : la dépendance se mesure par PAIRE DE
SIGNATURES (market_family + exposure_group + direction), jamais par paire
de matchs précis (deux matchs ne se reproduisent jamais à l'identique --
mesurer à ce niveau ne donnerait jamais assez d'observations).

Règle C, verrouillée par le bureau d'étude : une paire de signatures dont
la dépendance conjointe a moins de SEUIL_OBSERVATIONS_CONJOINTES
observations est déclarée NON MESURABLE -- ces deux types de jambes ne
peuvent jamais être combinés dans un ticket, quel que soit le contexte.

DÉCISION EXPLICITE PRISE ICI, PAS DANS LE DOCUMENT DU BUREAU D'ÉTUDE, À
CONFIRMER AVEC PATRICK : leur texte dit qu'une dépendance MESURABLE doit
être "acceptable" pour autoriser la combinaison, sans jamais définir ce
qui rend un D acceptable. BORNES_D_ACCEPTABLE = (1/1.3, 1.3) est une
valeur de départ RAISONNABLE MAIS NON VALIDÉE -- même statut que les
autres constantes non calibrées du projet (ROBUSTNESS_STD_THRESHOLD,
etc.) -- à réviser explicitement si l'expérience le justifie, jamais à
modifier ici sans une décision documentée.

Ce module NE MODIFIE JAMAIS les probabilités du moteur, ne recalibre
aucun λ, ne crée aucun coefficient permanent, n'introduit aucun 9e
paramètre calibrable dans garde_fous.PARAMETRES_CALIBRABLES, et
n'importe jamais selector.py/convergence.py/deduplication.py. Toute la
logique de corrélation reste strictement confinée à ce fichier.

Étant donné le volume de données actuel du projet (quelques dizaines
d'observations résolues par nuit), atteindre 100 observations conjointes
pour une paire de signatures prendra probablement plusieurs mois. **Il
est normal et attendu que ce module ne produise aucun ticket pendant
longtemps** -- ce n'est pas un bug, c'est la Règle C appliquée
honnêtement plutôt qu'un seuil abaissé pour "faire fonctionner" le
système prématurément.
"""

from __future__ import annotations

import re
from typing import Any

TAILLE_TICKET = 7
SEUIL_OBSERVATIONS_CONJOINTES = 100  # verrouillé par le bureau d'étude, 13/09/2026

# Voir avertissement en tête de fichier -- valeur de départ non validée.
BORNES_D_ACCEPTABLE = (1 / 1.3, 1.3)

_RE_OVER_UNDER_TOTAL = re.compile(r"^over_under_total_(-?\d+(?:\.\d+)?)_(over|under)$")
_RE_BUTS_EQUIPE = re.compile(r"^buts_equipe_(domicile|exterieur)_(-?\d+(?:\.\d+)?)_(over|under)$")
_RE_HANDICAP = re.compile(r"^handicap_(domicile|exterieur)_(-?\d+(?:\.\d+)?)$")
_RE_COMBO = re.compile(r"^combo_(1X|X2|12)_(over|under)_(-?\d+(?:\.\d+)?)$")


def direction_depuis_marche(marche: str | None) -> str:
    """Extrait la direction d'un marché -- reprend exactement les motifs
    déjà en production dans reglement.py, jamais une nouvelle convention.
    Retourne "INCONNUE" pour un marché non reconnu, jamais une exception
    (une signature avec direction inconnue reste utilisable, juste moins
    précise -- jamais un crash pour un marché encore non couvert ici)."""
    marche = (marche or "").strip()

    m = _RE_OVER_UNDER_TOTAL.match(marche)
    if m:
        return m.group(2).upper()
    if marche == "over_2_5":
        return "OVER"

    m = _RE_HANDICAP.match(marche)
    if m:
        return m.group(1).upper()

    if marche in ("double_chance_1X", "1x2_domicile"):
        return "1X"
    if marche in ("double_chance_X2", "1x2_exterieur"):
        return "X2"
    if marche == "double_chance_12":
        return "12"

    if marche == "btts_oui":
        return "OUI"
    if marche == "btts_non":
        return "NON"

    m = _RE_BUTS_EQUIPE.match(marche)
    if m:
        return f"{m.group(1).upper()}_{m.group(3).upper()}"

    if marche == "cage_inviolee_domicile":
        return "DOMICILE"
    if marche == "cage_inviolee_exterieur":
        return "EXTERIEUR"
    if marche == "encaisse_domicile":
        return "DOMICILE"
    if marche == "encaisse_exterieur":
        return "EXTERIEUR"

    if marche == "parite_pair":
        return "PAIR"
    if marche == "parite_impair":
        return "IMPAIR"

    m = _RE_COMBO.match(marche)
    if m:
        return f"{m.group(1)}_{m.group(2).upper()}"

    return "INCONNUE"


def signature(record: dict[str, Any]) -> tuple[Any, Any, str]:
    """market_family + exposure_group + direction -- la classe
    observable d'une jambe, jamais le marché exact avec sa ligne précise
    (over_2.5 et over_3.5 partagent la même signature -- assez fin pour
    être informatif, assez large pour accumuler des observations)."""
    return (
        record.get("market_family"),
        record.get("exposure_group"),
        direction_depuis_marche(record.get("marche")),
    )


def construire_marginal_et_matrice(
    records_resolus: list[dict[str, Any]],
) -> tuple[dict[tuple, dict[str, int]], dict[tuple, dict[str, int]]]:
    """Construit, à partir de l'archive résolue (SELECTED uniquement --
    jamais les COUNTERFACTUAL, qui n'ont jamais été de vrais paris) :
    - le marginal : pour chaque signature, nb observé / nb gagnant ;
    - la matrice de paires : pour chaque paire de signatures, le nombre
      d'observations CONJOINTES valides et le nombre de fois où les deux
      ont gagné ENSEMBLE.

    Une paire est valide si et seulement si les deux jambes proviennent
    de la MÊME JOURNÉE (date_match) mais de DEUX MATCHS DISTINCTS --
    jamais deux jambes du même match, jamais une paire fabriquée entre
    des journées différentes (romprait l'homogénéité temporelle voulue).
    """
    par_jour: dict[str, list[dict[str, Any]]] = {}
    for r in records_resolus:
        if r.get("resultat_marche") not in ("WIN", "LOSS"):
            continue
        par_jour.setdefault(r.get("date_match"), []).append(r)

    marginal: dict[tuple, dict[str, int]] = {}
    matrice: dict[tuple, dict[str, int]] = {}

    for jour_records in par_jour.values():
        for r in jour_records:
            sig = signature(r)
            bucket = marginal.setdefault(sig, {"total": 0, "gagnants": 0})
            bucket["total"] += 1
            if r.get("resultat_marche") == "WIN":
                bucket["gagnants"] += 1

        n = len(jour_records)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = jour_records[i], jour_records[j]
                if a.get("match_id") == b.get("match_id"):
                    continue  # jamais deux jambes du même match dans une paire
                cle = tuple(sorted((signature(a), signature(b))))
                bucket = matrice.setdefault(cle, {"conjointes": 0, "gagnantes_ensemble": 0})
                bucket["conjointes"] += 1
                if a.get("resultat_marche") == "WIN" and b.get("resultat_marche") == "WIN":
                    bucket["gagnantes_ensemble"] += 1

    return marginal, matrice


def probabilite_signature(sig: tuple, marginal: dict[tuple, dict[str, int]]) -> float | None:
    bucket = marginal.get(sig)
    if not bucket or bucket["total"] == 0:
        return None
    return bucket["gagnants"] / bucket["total"]


def dependance_paire(
    sig_a: tuple,
    sig_b: tuple,
    marginal: dict[tuple, dict[str, int]],
    matrice: dict[tuple, dict[str, int]],
    seuil_observations: int = SEUIL_OBSERVATIONS_CONJOINTES,
) -> dict[str, Any]:
    """Retourne toujours un dict avec au moins "mesurable" (bool). Si
    mesurable, contient aussi nb_observations_conjointes, p_a, p_b,
    p_conjointe, d. Ne lève jamais d'exception -- une donnée insuffisante
    est un résultat normal (mesurable=False), pas une erreur."""
    if sig_a == sig_b:
        return {"mesurable": True, "d": 1.0, "meme_signature": True, "nb_observations_conjointes": None}

    cle = tuple(sorted((sig_a, sig_b)))
    bucket = matrice.get(cle, {"conjointes": 0, "gagnantes_ensemble": 0})
    n = bucket["conjointes"]

    if n < seuil_observations:
        return {"mesurable": False, "nb_observations_conjointes": n}

    p_a = probabilite_signature(sig_a, marginal)
    p_b = probabilite_signature(sig_b, marginal)
    if not p_a or not p_b:
        return {"mesurable": False, "nb_observations_conjointes": n}

    p_conjointe = bucket["gagnantes_ensemble"] / n
    d = p_conjointe / (p_a * p_b)

    return {
        "mesurable": True,
        "nb_observations_conjointes": n,
        "p_a": p_a,
        "p_b": p_b,
        "p_conjointe": p_conjointe,
        "d": d,
    }


def paire_compatible(
    candidat_a: dict[str, Any],
    candidat_b: dict[str, Any],
    marginal: dict[tuple, dict[str, int]],
    matrice: dict[tuple, dict[str, int]],
    bornes_d: tuple[float, float] = BORNES_D_ACCEPTABLE,
    seuil_observations: int = SEUIL_OBSERVATIONS_CONJOINTES,
) -> tuple[bool, str]:
    """Deux jambes sont compatibles dans un même ticket si :
    1. elles ne proviennent PAS du même match (contrôle structurel, avant
       tout calcul de dépendance) ;
    2. leur dépendance de paire est mesurable (>= `seuil_observations`
       observations conjointes) ;
    3. leur D mesuré tombe dans `bornes_d` (proche de l'indépendance).

    `seuil_observations` et `bornes_d` sont explicitement paramétrables
    (ajout du 13/09/2026, mode observation) -- un vrai ticket utilise
    TOUJOURS les valeurs par défaut (SEUIL_OBSERVATIONS_CONJOINTES=100,
    BORNES_D_ACCEPTABLE), jamais changées silencieusement ; seul
    tickets/observation.py appelle cette fonction avec un seuil abaissé,
    et uniquement pour des tickets fictifs jamais présentés comme réels.

    Retourne (compatible, motif) -- motif toujours renseigné en cas
    d'incompatibilité, jamais un simple booléen muet."""
    if candidat_a.get("match_id") == candidat_b.get("match_id"):
        return False, "même match -- jamais deux jambes du même match dans un ticket"

    dep = dependance_paire(
        signature(candidat_a), signature(candidat_b), marginal, matrice,
        seuil_observations=seuil_observations,
    )
    if not dep["mesurable"]:
        return False, (
            f"dépendance non mesurable ({dep['nb_observations_conjointes']} "
            f"< {seuil_observations} observations conjointes requises)"
        )

    d = dep.get("d")
    if d is None or not (bornes_d[0] <= d <= bornes_d[1]):
        return False, f"dépendance mesurée mais hors bornes acceptables (D={d})"

    return True, ""


def construire_ticket(
    candidats: list[dict[str, Any]],
    marginal: dict[tuple, dict[str, int]],
    matrice: dict[tuple, dict[str, int]],
    taille: int = TAILLE_TICKET,
    bornes_d: tuple[float, float] = BORNES_D_ACCEPTABLE,
    seuil_observations: int = SEUIL_OBSERVATIONS_CONJOINTES,
) -> dict[str, Any] | None:
    """Construit UN ticket de `taille` jambes par sélection gloutonne
    (les candidats triés par EDV décroissant, chacun ajouté seulement
    s'il est compatible avec TOUTES les jambes déjà retenues).

    `bornes_d`/`seuil_observations` : voir paire_compatible -- un vrai
    ticket n'utilise jamais d'autres valeurs que les valeurs par défaut.

    Retourne None si moins de `taille` jambes compatibles n'ont pu être
    réunies -- JAMAIS un ticket incomplet, jamais un critère dégradé
    pour atteindre le quota (règle explicite du bureau d'étude, 12/09)."""
    candidats_tries = sorted(candidats, key=lambda c: c.get("edv") or 0, reverse=True)
    retenus: list[dict[str, Any]] = []

    for candidat in candidats_tries:
        if len(retenus) >= taille:
            break
        if all(
            paire_compatible(candidat, r, marginal, matrice, bornes_d, seuil_observations)[0]
            for r in retenus
        ):
            retenus.append(candidat)

    if len(retenus) < taille:
        return None

    probabilite_ticket = 1.0
    for c in retenus:
        probabilite_ticket *= c.get("probabilite") or 0

    return {
        "jambes": retenus,
        "taille": len(retenus),
        "probabilite_ticket": probabilite_ticket,
        "methode_probabilite": (
            "produit des probabilités individuelles -- valide uniquement "
            "parce que chaque paire de jambes retenues a une dépendance "
            "mesurée proche de l'indépendance (voir paire_compatible)"
        ),
    }
