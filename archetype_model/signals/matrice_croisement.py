"""
archetype_model/signals/matrice_croisement.py — Matrice de croisement
des profils qualitatifs domicile/extérieur (demande explicite de
Patrick, 16/09/2026, points 2-3).

PRINCIPE (dans l'ordre voulu par Patrick, ne pas inverser) :
    1. profil_equipe.construit_profil() -- valeur réelle de chaque
       équipe SUR SON RÔLE (ce module ne calcule rien lui-même,
       il consomme les deux profils déjà construits).
    2. CE MODULE -- croise les deux profils sur plusieurs dimensions
       indépendantes pour faire apparaître des TENDANCES NETTES avant
       tout calcul de lambda/EDV.
    3. lambda/EDV/robustesse (main.py, poisson/, edv/) arbitrent
       ENSUITE entre les tendances qui ressortent ici -- ce module ne
       calcule ni lambda ni EDV, ne consulte aucune cote, et n'écrit
       jamais dans candidats/selector.py.

Chaque "règle de croisement" ci-dessous combine UNE statistique de
l'équipe domicile (sur sa fenêtre domicile) et UNE statistique de
l'équipe extérieure (sur sa fenêtre extérieure) -- jamais les deux
statistiques de la même équipe entre elles, jamais domicile+domicile
ou extérieur+extérieur des deux côtés (ça reproduirait juste un profil
plutôt que de croiser deux équipes).

Chaque signal reste accompagné du détail de ses dimensions (jamais
caché) et d'un `score_pondere` (nb_dimensions_convergentes x poids de
fiabilité croisé), calculé ici en une seule passe -- demande explicite
de Patrick le 16/09/2026 pour ne pas avoir à relire la fiabilité
séparément à chaque fois. Nuance à garder en tête : ça reste UN
score par marché, jamais un score unique fusionnant plusieurs marchés
différents (over/under, BTTS, résultat...) -- cette fusion-là n'existe
toujours pas et reste refusée. Trier et choisir entre plusieurs
signaux convergents pour le même marché est le rôle de
selector.py/convergence.py EN AVAL, jamais fait ici.
"""

from __future__ import annotations

from typing import Any

SEUIL_HAUT = 0.60   # fréquence au-dessus de laquelle une tendance est jugée "forte"
SEUIL_BAS = 0.40    # fréquence en-dessous de laquelle une tendance est jugée "forte" dans l'autre sens


def _niveau_fiabilite_croise(profil_a: dict, profil_b: dict) -> str:
    """Un croisement n'est fiable que si les DEUX profils le sont --
    la fiabilité d'une paire est celle du maillon le plus faible,
    jamais une moyenne qui masquerait un des deux côtés trop petit."""
    from ..statistics.profil_equipe import STATUT_FIABLE
    if profil_a["statut_fiabilite"] == STATUT_FIABLE and profil_b["statut_fiabilite"] == STATUT_FIABLE:
        return STATUT_FIABLE
    return "A_SURVEILLER"


def _poids_fiabilite_croise(profil_a: dict, profil_b: dict) -> float:
    """Version numérique de _niveau_fiabilite_croise -- le maillon le
    plus faible des deux profils (jamais une moyenne, qui masquerait
    un des deux côtés trop petit)."""
    return min(profil_a["poids_fiabilite"], profil_b["poids_fiabilite"])


def _ajoute(signaux: list[dict], marche: str, direction: str, poids_dimensions: list[tuple[str, float]],
            fiabilite: str, poids_fiabilite_num: float):
    """poids_dimensions : liste de (nom_dimension, valeur_frequence)
    qui pointent TOUTES dans la même direction pour ce marché -- le
    nombre de dimensions convergentes reste visible en détail (jamais
    caché), mais score_pondere combine ce nombre ET la fiabilité
    réelle de l'échantillon en UNE seule valeur, calculée ici, pour ne
    pas obliger à relire la fiabilité séparément à chaque fois."""
    n_dims = len(poids_dimensions)
    signaux.append({
        "marche": marche,
        "direction": direction,
        "nb_dimensions_convergentes": n_dims,
        "dimensions": [{"nom": nom, "valeur": val} for nom, val in poids_dimensions],
        "fiabilite": fiabilite,
        "poids_fiabilite": poids_fiabilite_num,
        "score_pondere": n_dims * poids_fiabilite_num,
    })


def croise_profils(profil_domicile: dict[str, Any], profil_exterieur: dict[str, Any]) -> list[dict[str, Any]]:
    """Croise le profil de l'équipe à domicile (sur sa fenêtre
    domicile) avec le profil de l'équipe à l'extérieur (sur sa fenêtre
    extérieure), et retourne une liste de signaux de tendance, triée
    par nombre de dimensions convergentes décroissant (les tendances
    les plus corroborées en premier -- l'arbitrage final EDV/lambda
    reste en aval, ce tri n'est qu'un ordre de lecture)."""
    fiabilite = _niveau_fiabilite_croise(profil_domicile, profil_exterieur)
    poids_num = _poids_fiabilite_croise(profil_domicile, profil_exterieur)
    signaux: list[dict] = []

    a_off, a_def, a_res, a_bt = (profil_domicile["attaque"], profil_domicile["defense"],
                                 profil_domicile["resultats"], profil_domicile["tendances_buts"])
    b_off, b_def, b_res, b_bt = (profil_exterieur["attaque"], profil_exterieur["defense"],
                                 profil_exterieur["resultats"], profil_exterieur["tendances_buts"])

    # --- "Plus de buts équipe domicile" : coeur obligatoire = freq/marge
    # réelles (pas seulement des séries courtes, qui seules ont permis à
    # domicile_plus ET exterieur_plus de sortir en même temps -- trouvé
    # par test). Séries en soutien uniquement, jamais suffisantes seules.
    coeur = []
    if a_off["freq_marque_2_plus"] is not None and a_off["freq_marque_2_plus"] >= SEUIL_HAUT:
        coeur.append(("attaque_domicile_freq_marque_2+", a_off["freq_marque_2_plus"]))
    if b_def["freq_encaisse_2_plus"] is not None and b_def["freq_encaisse_2_plus"] >= SEUIL_HAUT:
        coeur.append(("defense_exterieur_freq_encaisse_2+", b_def["freq_encaisse_2_plus"]))
    if a_res["marge_buts_moyenne"] is not None and a_res["marge_buts_moyenne"] > 0:
        coeur.append(("marge_buts_domicile", a_res["marge_buts_moyenne"]))
    soutien = []
    if a_off["serie_marque_actuelle"] >= 2:
        soutien.append(("serie_marque_domicile", a_off["serie_marque_actuelle"]))
    if b_def["serie_encaisse_actuelle"] >= 2:
        soutien.append(("serie_encaisse_exterieur", b_def["serie_encaisse_actuelle"]))
    if len(coeur) >= 1 and len(coeur) + len(soutien) >= 2:
        _ajoute(signaux, "buts_equipe_domicile_plus", "favorable", coeur + soutien, fiabilite, poids_num)

    # --- "Plus de buts équipe extérieure" : symétrique ---
    coeur = []
    if b_off["freq_marque_2_plus"] is not None and b_off["freq_marque_2_plus"] >= SEUIL_HAUT:
        coeur.append(("attaque_exterieur_freq_marque_2+", b_off["freq_marque_2_plus"]))
    if a_def["freq_encaisse_2_plus"] is not None and a_def["freq_encaisse_2_plus"] >= SEUIL_HAUT:
        coeur.append(("defense_domicile_freq_encaisse_2+", a_def["freq_encaisse_2_plus"]))
    if b_res["marge_buts_moyenne"] is not None and b_res["marge_buts_moyenne"] > 0:
        coeur.append(("marge_buts_exterieur", b_res["marge_buts_moyenne"]))
    soutien = []
    if b_off["serie_marque_actuelle"] >= 2:
        soutien.append(("serie_marque_exterieur", b_off["serie_marque_actuelle"]))
    if a_def["serie_encaisse_actuelle"] >= 2:
        soutien.append(("serie_encaisse_domicile", a_def["serie_encaisse_actuelle"]))
    if len(coeur) >= 1 and len(coeur) + len(soutien) >= 2:
        _ajoute(signaux, "buts_equipe_exterieur_plus", "favorable", coeur + soutien, fiabilite, poids_num)

    # --- BTTS oui : coeur obligatoire = freq/clean-sheet réelles, séries en soutien ---
    coeur = []
    if a_bt["freq_btts"] is not None and a_bt["freq_btts"] >= SEUIL_HAUT:
        coeur.append(("btts_domicile", a_bt["freq_btts"]))
    if b_bt["freq_btts"] is not None and b_bt["freq_btts"] >= SEUIL_HAUT:
        coeur.append(("btts_exterieur", b_bt["freq_btts"]))
    if a_def["freq_clean_sheet"] is not None and a_def["freq_clean_sheet"] <= SEUIL_BAS:
        coeur.append(("faible_clean_sheet_domicile", a_def["freq_clean_sheet"]))
    if b_def["freq_clean_sheet"] is not None and b_def["freq_clean_sheet"] <= SEUIL_BAS:
        coeur.append(("faible_clean_sheet_exterieur", b_def["freq_clean_sheet"]))
    soutien = []
    if a_bt["serie_btts_oui_actuelle"] >= 2:
        soutien.append(("serie_btts_oui_domicile", a_bt["serie_btts_oui_actuelle"]))
    if b_bt["serie_btts_oui_actuelle"] >= 2:
        soutien.append(("serie_btts_oui_exterieur", b_bt["serie_btts_oui_actuelle"]))
    if len(coeur) >= 1 and len(coeur) + len(soutien) >= 2:
        _ajoute(signaux, "btts_oui", "favorable", coeur + soutien, fiabilite, poids_num)

    # --- BTTS non : symétrique ---
    coeur = []
    if a_def["freq_clean_sheet"] is not None and a_def["freq_clean_sheet"] >= SEUIL_HAUT:
        coeur.append(("forte_clean_sheet_domicile", a_def["freq_clean_sheet"]))
    if b_off["freq_marque_0"] is not None and b_off["freq_marque_0"] >= SEUIL_BAS:
        coeur.append(("exterieur_freq_marque_0", b_off["freq_marque_0"]))
    soutien = []
    if a_bt["serie_btts_non_actuelle"] >= 2:
        soutien.append(("serie_btts_non_domicile", a_bt["serie_btts_non_actuelle"]))
    if b_bt["serie_btts_non_actuelle"] >= 2:
        soutien.append(("serie_btts_non_exterieur", b_bt["serie_btts_non_actuelle"]))
    if a_def["serie_clean_sheet_actuelle"] >= 2:
        soutien.append(("serie_clean_sheet_domicile", a_def["serie_clean_sheet_actuelle"]))
    if b_off["serie_sans_marquer_actuelle"] >= 2:
        soutien.append(("serie_sans_marquer_exterieur", b_off["serie_sans_marquer_actuelle"]))
    if len(coeur) >= 1 and len(coeur) + len(soutien) >= 2:
        _ajoute(signaux, "btts_non", "favorable", coeur + soutien, fiabilite, poids_num)

    # --- Over 2.5 : la fréquence over 2.5 elle-même est OBLIGATOIRE (coeur) ;
    # l'activité offensive des deux équipes est un simple renfort, jamais
    # suffisante seule -- sinon over_2.5 et under_2.5 peuvent sortir en
    # même temps sur le même match (contradiction trouvée par test).
    coeur = []
    if a_bt["freq_over_2_5"] is not None and a_bt["freq_over_2_5"] >= SEUIL_HAUT:
        coeur.append(("over_2.5_domicile", a_bt["freq_over_2_5"]))
    if b_bt["freq_over_2_5"] is not None and b_bt["freq_over_2_5"] >= SEUIL_HAUT:
        coeur.append(("over_2.5_exterieur", b_bt["freq_over_2_5"]))
    soutien = []
    if a_off["freq_marque_1_plus"] is not None and a_off["freq_marque_1_plus"] >= SEUIL_HAUT:
        soutien.append(("attaque_domicile_active", a_off["freq_marque_1_plus"]))
    if b_off["freq_marque_1_plus"] is not None and b_off["freq_marque_1_plus"] >= SEUIL_HAUT:
        soutien.append(("attaque_exterieur_active", b_off["freq_marque_1_plus"]))
    if a_bt["serie_over_2_5_actuelle"] >= 2:
        soutien.append(("serie_over_2.5_domicile", a_bt["serie_over_2_5_actuelle"]))
    if b_bt["serie_over_2_5_actuelle"] >= 2:
        soutien.append(("serie_over_2.5_exterieur", b_bt["serie_over_2_5_actuelle"]))
    if len(coeur) >= 1 and len(coeur) + len(soutien) >= 2:
        _ajoute(signaux, "over_2_5", "favorable", coeur + soutien, fiabilite, poids_num)

    # --- Under 2.5 : symétrique, coeur obligatoire = freq_over_2_5 basse ---
    coeur = []
    if a_bt["freq_over_2_5"] is not None and a_bt["freq_over_2_5"] <= SEUIL_BAS:
        coeur.append(("under_2.5_domicile", 1 - a_bt["freq_over_2_5"]))
    if b_bt["freq_over_2_5"] is not None and b_bt["freq_over_2_5"] <= SEUIL_BAS:
        coeur.append(("under_2.5_exterieur", 1 - b_bt["freq_over_2_5"]))
    soutien = []
    if a_def["freq_clean_sheet"] is not None and a_def["freq_clean_sheet"] >= SEUIL_HAUT:
        soutien.append(("defense_domicile_solide", a_def["freq_clean_sheet"]))
    if b_def["freq_clean_sheet"] is not None and b_def["freq_clean_sheet"] >= SEUIL_HAUT:
        soutien.append(("defense_exterieur_solide", b_def["freq_clean_sheet"]))
    if a_bt["serie_under_2_5_actuelle"] >= 2:
        soutien.append(("serie_under_2.5_domicile", a_bt["serie_under_2_5_actuelle"]))
    if b_bt["serie_under_2_5_actuelle"] >= 2:
        soutien.append(("serie_under_2.5_exterieur", b_bt["serie_under_2_5_actuelle"]))
    if len(coeur) >= 1 and len(coeur) + len(soutien) >= 2:
        _ajoute(signaux, "under_2_5", "favorable", coeur + soutien, fiabilite, poids_num)

    # --- Domination nette domicile (résultat) : forme + marge + résultats convergent ---
    dims = []
    if a_res["forme_ponderee_recence"] is not None and a_res["forme_ponderee_recence"] >= 2.0:
        dims.append(("forme_recente_domicile", a_res["forme_ponderee_recence"]))
    if b_res["forme_ponderee_recence"] is not None and b_res["forme_ponderee_recence"] <= 1.0:
        dims.append(("forme_recente_exterieur_faible", b_res["forme_ponderee_recence"]))
    if a_res["freq_victoires"] is not None and a_res["freq_victoires"] >= SEUIL_HAUT:
        dims.append(("freq_victoires_domicile", a_res["freq_victoires"]))
    if b_res["freq_defaites"] is not None and b_res["freq_defaites"] >= SEUIL_HAUT:
        dims.append(("freq_defaites_exterieur", b_res["freq_defaites"]))
    if len(dims) >= 2:
        _ajoute(signaux, "resultat_domicile", "favorable", dims, fiabilite, poids_num)

    # RÉSOLUTION FINALE (garde-fou générique, trouvé nécessaire par test
    # 16/09/2026) : le cœur/soutien de chaque règle empêche une
    # contradiction DANS le même camp de dimensions, mais pas le cas où
    # l'équipe domicile justifie un marché et l'équipe extérieure
    # justifie SEULE son opposé (ex. domicile pousse vers BTTS-oui,
    # extérieur pousse vers BTTS-non) -- un vrai conflit de preuves,
    # pas une erreur de calcul. Dans ce cas il n'y a PAS de tendance
    # nette (le but même de cette matrice), donc : le marché avec le
    # plus de dimensions convergentes gagne ; à égalité stricte, aucun
    # des deux n'est assez net, les deux sont retirés.
    opposes = {
        "over_2_5": "under_2_5", "under_2_5": "over_2_5",
        "btts_oui": "btts_non", "btts_non": "btts_oui",
        "buts_equipe_domicile_plus": "buts_equipe_exterieur_plus",
        "buts_equipe_exterieur_plus": "buts_equipe_domicile_plus",
    }
    par_marche = {s["marche"]: s for s in signaux}
    a_retirer = set()
    for marche, oppose in opposes.items():
        if marche in a_retirer or oppose in a_retirer:
            continue
        if marche in par_marche and oppose in par_marche:
            score_marche = par_marche[marche]["score_pondere"]
            score_oppose = par_marche[oppose]["score_pondere"]
            if score_marche > score_oppose:
                a_retirer.add(oppose)
            elif score_oppose > score_marche:
                a_retirer.add(marche)
            else:
                a_retirer.add(marche)
                a_retirer.add(oppose)
    signaux = [s for s in signaux if s["marche"] not in a_retirer]

    signaux.sort(key=lambda s: s["score_pondere"], reverse=True)
    return signaux
