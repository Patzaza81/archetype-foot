"""
adapte_justification.py — (04/09/2026 soir) fait le pont entre les vraies
données déjà collectées par le pipeline et moteur_justification.py.

moteur_justification.py ne calcule RIEN par contrat -- il attend des
PreuveStatistique déjà calculées et vérifiées (voir son en-tête). Ce fichier
est le SEUL endroit qui a le droit de transformer des matchs bruts en
pourcentages/moyennes, en réutilisant explicitement les mêmes règles de
marché que le reste du système :

- Pour les marchés SYMÉTRIQUES (le résultat ne dépend pas de qui est
  domicile/extérieur : Plus/Moins de X buts, BTTS, Pair/Impair, Nombre
  exact de buts) -- réutilise calcule_roi.verifie_pari() TEL QUEL, pour ne
  jamais avoir deux définitions différentes du même marché dans le dépôt
  (une pour le calcul du pari, une pour sa justification). Vérifié :
  toutes les règles symétriques ci-dessus donnent le même résultat qu'on
  passe (a, b) ou (b, a) -- x>0 and y>0, (x+y)%2, (x+y)>seuil sont tous
  commutatifs.
- Pour les marchés qui dépendent du côté (1X2, Double chance, Handicap,
  Cage inviolée, Sans but, Plus/Moins de X buts - Domicile/Extérieur) --
  verifie_pari() ne peut PAS être réutilisé tel quel sur l'historique
  PROPRE d'une équipe (un match où l'équipe jouait à l'extérieur n'a pas
  ses propres buts en position "buts_domicile"). Logique dédiée ci-dessous,
  qui n'utilise que buts_marques/buts_encaisses du point de vue de
  l'équipe elle-même.
- Handicap et Score exact : AUCUNE preuve construite pour ces marchés --
  pas de règle fiable et déjà testée pour les évaluer sur un historique
  d'équipe orienté domicile/extérieur sans risque de contresens. Mieux
  vaut n'afficher aucune justification que d'en afficher une fausse.

Ordre des matchs bruts (matchs_domicile_bruts/matchs_exterieur_bruts,
sortie de recupere_gf_ga_avec_repli) : PAS D'HYPOTHÈSE FAITE sur l'ordre
chronologique -- calculé comme une fréquence sur l'échantillon disponible,
jamais présenté comme une "série récente".
"""

from typing import List, Optional

import calcule_roi
from moteur_justification import (
    PreuveStatistique,
    TYPE_FREQUENCE_MARCHE,
    TYPE_MOYENNE_BUTS_TOTAUX,
    TYPE_MOYENNE_BUTS_MARQUES,
    TYPE_BTTS,
    TYPE_CLEAN_SHEET,
    TYPE_SANS_BUT,
    TYPE_H2H_MARCHE,
    identifie_type_marche,
)

MARCHES_SYMETRIQUES = {"OVER_UNDER_MATCH", "BTTS", "PAIR_IMPAIR", "NOMBRE_EXACT_BUTS"}


def _marche_sans_suffixe_cote(marche: str) -> str:
    """'Plus de 1.5 buts - Domicile' -> 'Plus de 1.5 buts' (forme symétrique,
    utilisée uniquement pour évaluer un marché sur un historique H2H où
    'domicile'/'extérieur' n'a pas de sens du point de vue justification)."""
    for suffixe in (" - Domicile", " - Extérieur"):
        if marche.endswith(suffixe):
            return marche[: -len(suffixe)]
    return marche


def _frequence_sur_matchs(marche: str, matchs: List[dict]) -> Optional[tuple]:
    """Compte, sur une liste de matchs bruts {buts_marques, buts_encaisses},
    combien vérifient réellement `marche` (réutilise calcule_roi.verifie_pari).
    Renvoie (occurrences, total) ou None si le marché n'est pas reconnu ou
    la liste est vide -- jamais un pourcentage inventé sur 0 match."""
    if not matchs:
        return None
    occurrences, total = 0, 0
    for m in matchs:
        resultat = calcule_roi.verifie_pari(marche, m["buts_marques"], m["buts_encaisses"])
        if resultat is None:
            continue
        total += 1
        if resultat:
            occurrences += 1
    if total == 0:
        return None
    return occurrences, total


def _preuve_frequence(marche_evaluee, matchs, libelle, contexte, source, equipe=None):
    compte = _frequence_sur_matchs(marche_evaluee, matchs)
    if compte is None:
        return None
    occurrences, total = compte
    return PreuveStatistique(
        type=TYPE_FREQUENCE_MARCHE,
        contexte=contexte,
        libelle=libelle,
        occurrences=occurrences,
        total=total,
        pourcentage=round(occurrences / total * 100, 1),
        source=source,
        verifie=True,
        equipe=equipe,
    )


def _preuve_moyenne_totaux(matchs, contexte, source) -> Optional[PreuveStatistique]:
    if not matchs:
        return None
    totaux = [m["buts_marques"] + m["buts_encaisses"] for m in matchs]
    return PreuveStatistique(
        type=TYPE_MOYENNE_BUTS_TOTAUX,
        contexte=contexte,
        libelle="Moyenne totale de buts",
        moyenne=round(sum(totaux) / len(totaux), 2),
        source=source,
        verifie=True,
    )


def _preuve_moyenne_marques(matchs, contexte, source, equipe) -> Optional[PreuveStatistique]:
    if not matchs:
        return None
    valeurs = [m["buts_marques"] for m in matchs]
    return PreuveStatistique(
        type=TYPE_MOYENNE_BUTS_MARQUES,
        contexte=contexte,
        libelle="Moyenne de buts marqués",
        moyenne=round(sum(valeurs) / len(valeurs), 2),
        source=source,
        verifie=True,
        equipe=equipe,
    )


def _preuve_clean_sheet(matchs, contexte, source, equipe) -> Optional[PreuveStatistique]:
    if not matchs:
        return None
    occurrences = sum(1 for m in matchs if m["buts_encaisses"] == 0)
    total = len(matchs)
    return PreuveStatistique(
        type=TYPE_CLEAN_SHEET,
        contexte=contexte,
        libelle="Cage inviolée",
        occurrences=occurrences,
        total=total,
        pourcentage=round(occurrences / total * 100, 1),
        source=source,
        verifie=True,
        equipe=equipe,
    )


def _preuve_sans_but(matchs, contexte, source, equipe) -> Optional[PreuveStatistique]:
    """'Sans but' = l'équipe n'a pas marqué (buts_marques == 0) -- distinct
    de 'cage inviolée' (l'adversaire n'a pas marqué). Convention à confirmer
    avec Patrick si elle ne correspond pas à l'usage voulu."""
    if not matchs:
        return None
    occurrences = sum(1 for m in matchs if m["buts_marques"] == 0)
    total = len(matchs)
    return PreuveStatistique(
        type=TYPE_SANS_BUT,
        contexte=contexte,
        libelle="Sans marquer",
        occurrences=occurrences,
        total=total,
        pourcentage=round(occurrences / total * 100, 1),
        source=source,
        verifie=True,
        equipe=equipe,
    )


def _preuve_h2h(marche: str, h2h_brut: List[dict]) -> Optional[PreuveStatistique]:
    """H2H : toujours évalué sous forme symétrique (le marché ne distingue
    pas qui était domicile dans CES confrontations passées)."""
    if not h2h_brut:
        return None
    marche_symetrique = _marche_sans_suffixe_cote(marche)
    occurrences, total = 0, 0
    for m in h2h_brut:
        resultat = calcule_roi.verifie_pari(marche_symetrique, m["buts_domicile"], m["buts_exterieur"])
        if resultat is None:
            continue
        total += 1
        if resultat:
            occurrences += 1
    if total == 0:
        return None
    return PreuveStatistique(
        type=TYPE_H2H_MARCHE,
        contexte=f"{total} dernières confrontations directes",
        libelle=marche_symetrique,
        occurrences=occurrences,
        total=total,
        pourcentage=round(occurrences / total * 100, 1),
        source="h2h",
        verifie=True,
    )


def construit_preuves(
    marche: str,
    matchs_domicile_bruts: List[dict],
    matchs_exterieur_bruts: List[dict],
    h2h_brut: List[dict],
    nom_domicile: str,
    nom_exterieur: str,
) -> List[PreuveStatistique]:
    """
    Construit la liste de PreuveStatistique réellement vérifiables pour le
    marché du pronostic recommandé (`marche`), à partir des matchs bruts
    déjà collectés par le pipeline. Ne fabrique jamais un fait pour un
    marché qu'elle ne sait pas évaluer honnêtement (Handicap, Score exact
    -> liste vide pour ces marchés, moteur_justification.py gère déjà
    l'absence de preuve sans planter).
    """
    type_marche = identifie_type_marche(marche)
    preuves: List[PreuveStatistique] = []

    ctx_dom = f"Domicile -- {len(matchs_domicile_bruts)} derniers matchs"
    ctx_ext = f"Extérieur -- {len(matchs_exterieur_bruts)} derniers matchs"

    if type_marche in MARCHES_SYMETRIQUES:
        p = _preuve_frequence(marche, matchs_domicile_bruts, marche, ctx_dom,
                               "historique_equipe_domicile", equipe=nom_domicile)
        if p:
            preuves.append(p)
        p = _preuve_frequence(marche, matchs_exterieur_bruts, marche, ctx_ext,
                               "historique_equipe_exterieure", equipe=nom_exterieur)
        if p:
            preuves.append(p)
        p = _preuve_moyenne_totaux(matchs_domicile_bruts + matchs_exterieur_bruts,
                                    "Matchs récents combinés", "historique_combine")
        if p:
            preuves.append(p)

    elif type_marche == "OVER_UNDER_EQUIPE":
        cible_matchs = matchs_domicile_bruts if "domicile" in marche.lower() else matchs_exterieur_bruts
        ctx = ctx_dom if "domicile" in marche.lower() else ctx_ext
        source = "historique_equipe_domicile" if "domicile" in marche.lower() else "historique_equipe_exterieure"
        equipe = nom_domicile if "domicile" in marche.lower() else nom_exterieur
        # Réévalue en forme symétrique (sans suffixe) sur les buts marqués
        # SEULS de l'équipe -- verifie_pari attend (buts_domicile,
        # buts_exterieur), donc on passe (buts_marques, 0) et on regarde
        # uniquement le seuil de but marqué -- construit la règle localement
        # plutôt que de détourner verifie_pari hors de son usage prévu.
        import re
        m_seuil = re.match(r"^(Plus|Moins) de (\d+(?:\.\d+)?) buts", marche)
        if m_seuil and cible_matchs:
            sens, seuil = m_seuil.group(1), float(m_seuil.group(2))
            occurrences = sum(
                1 for m in cible_matchs
                if (m["buts_marques"] > seuil) == (sens == "Plus")
            )
            total = len(cible_matchs)
            preuves.append(PreuveStatistique(
                type=TYPE_FREQUENCE_MARCHE, contexte=ctx, libelle=marche,
                occurrences=occurrences, total=total,
                pourcentage=round(occurrences / total * 100, 1),
                source=source, verifie=True, equipe=equipe,
            ))
        p = _preuve_moyenne_marques(cible_matchs, ctx, source, equipe)
        if p:
            preuves.append(p)

    elif type_marche == "CLEAN_SHEET":
        cible = matchs_domicile_bruts if "domicile" in marche.lower() else matchs_exterieur_bruts
        ctx = ctx_dom if "domicile" in marche.lower() else ctx_ext
        source = "historique_equipe_domicile" if "domicile" in marche.lower() else "historique_equipe_exterieure"
        equipe = nom_domicile if "domicile" in marche.lower() else nom_exterieur
        p = _preuve_clean_sheet(cible, ctx, source, equipe)
        if p:
            preuves.append(p)

    elif type_marche == "SANS_BUT":
        cible = matchs_domicile_bruts if "domicile" in marche.lower() else matchs_exterieur_bruts
        ctx = ctx_dom if "domicile" in marche.lower() else ctx_ext
        source = "historique_equipe_domicile" if "domicile" in marche.lower() else "historique_equipe_exterieure"
        equipe = nom_domicile if "domicile" in marche.lower() else nom_exterieur
        p = _preuve_sans_but(cible, ctx, source, equipe)
        if p:
            preuves.append(p)

    # 1X2 / DOUBLE_CHANCE / HANDICAP / SCORE_EXACT : aucune preuve fiable
    # construite ici pour l'instant (voir en-tête). moteur_justification.py
    # affichera alors uniquement les preuves H2H ci-dessous s'il y en a.

    p = _preuve_h2h(marche, h2h_brut)
    if p:
        preuves.append(p)

    return preuves
