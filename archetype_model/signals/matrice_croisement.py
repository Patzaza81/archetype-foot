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

Le résultat n'est jamais un score composite unique (cohérent avec le
principe déjà établi dans statistiques_signal.py : "jamais offensif +
défensif + tendance comptés séparément") -- c'est une LISTE de signaux
de croisement, chacun avec son marché visé, sa direction, et le nombre
de dimensions indépendantes qui pointent dans le même sens. Trier et
choisir entre plusieurs signaux convergents pour le même marché est le
rôle de selector.py/convergence.py EN AVAL, jamais fait ici.
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


def _ajoute(signaux: list[dict], marche: str, direction: str, poids_dimensions: list[tuple[str, float]], fiabilite: str):
    """poids_dimensions : liste de (nom_dimension, valeur_frequence)
    qui pointent TOUTES dans la même direction pour ce marché -- le
    nombre de dimensions convergentes EST l'information à faire
    ressortir, jamais réduite à une seule valeur agrégée."""
    signaux.append({
        "marche": marche,
        "direction": direction,
        "nb_dimensions_convergentes": len(poids_dimensions),
        "dimensions": [{"nom": nom, "valeur": val} for nom, val in poids_dimensions],
        "fiabilite": fiabilite,
    })


def croise_profils(profil_domicile: dict[str, Any], profil_exterieur: dict[str, Any]) -> list[dict[str, Any]]:
    """Croise le profil de l'équipe à domicile (sur sa fenêtre
    domicile) avec le profil de l'équipe à l'extérieur (sur sa fenêtre
    extérieure), et retourne une liste de signaux de tendance, triée
    par nombre de dimensions convergentes décroissant (les tendances
    les plus corroborées en premier -- l'arbitrage final EDV/lambda
    reste en aval, ce tri n'est qu'un ordre de lecture)."""
    fiabilite = _niveau_fiabilite_croise(profil_domicile, profil_exterieur)
    signaux: list[dict] = []

    a_off, a_def, a_res, a_bt = (profil_domicile["attaque"], profil_domicile["defense"],
                                 profil_domicile["resultats"], profil_domicile["tendances_buts"])
    b_off, b_def, b_res, b_bt = (profil_exterieur["attaque"], profil_exterieur["defense"],
                                 profil_exterieur["resultats"], profil_exterieur["tendances_buts"])

    # --- "Plus de buts équipe domicile" : A marque souvent ET B encaisse souvent à l'extérieur ---
    dims = []
    if a_off["freq_marque_2_plus"] is not None and a_off["freq_marque_2_plus"] >= SEUIL_HAUT:
        dims.append(("attaque_domicile_freq_marque_2+", a_off["freq_marque_2_plus"]))
    if b_def["freq_encaisse_2_plus"] is not None and b_def["freq_encaisse_2_plus"] >= SEUIL_HAUT:
        dims.append(("defense_exterieur_freq_encaisse_2+", b_def["freq_encaisse_2_plus"]))
    if a_res["marge_buts_moyenne"] is not None and a_res["marge_buts_moyenne"] > 0:
        dims.append(("marge_buts_domicile", a_res["marge_buts_moyenne"]))
    if len(dims) >= 2:
        _ajoute(signaux, "buts_equipe_domicile_plus", "favorable", dims, fiabilite)

    # --- "Plus de buts équipe extérieure" : symétrique ---
    dims = []
    if b_off["freq_marque_2_plus"] is not None and b_off["freq_marque_2_plus"] >= SEUIL_HAUT:
        dims.append(("attaque_exterieur_freq_marque_2+", b_off["freq_marque_2_plus"]))
    if a_def["freq_encaisse_2_plus"] is not None and a_def["freq_encaisse_2_plus"] >= SEUIL_HAUT:
        dims.append(("defense_domicile_freq_encaisse_2+", a_def["freq_encaisse_2_plus"]))
    if b_res["marge_buts_moyenne"] is not None and b_res["marge_buts_moyenne"] > 0:
        dims.append(("marge_buts_exterieur", b_res["marge_buts_moyenne"]))
    if len(dims) >= 2:
        _ajoute(signaux, "buts_equipe_exterieur_plus", "favorable", dims, fiabilite)

    # --- BTTS oui : les deux équipes marquent souvent ET encaissent souvent ---
    dims = []
    if a_bt["freq_btts"] is not None and a_bt["freq_btts"] >= SEUIL_HAUT:
        dims.append(("btts_domicile", a_bt["freq_btts"]))
    if b_bt["freq_btts"] is not None and b_bt["freq_btts"] >= SEUIL_HAUT:
        dims.append(("btts_exterieur", b_bt["freq_btts"]))
    if a_def["freq_clean_sheet"] is not None and a_def["freq_clean_sheet"] <= SEUIL_BAS:
        dims.append(("faible_clean_sheet_domicile", a_def["freq_clean_sheet"]))
    if b_def["freq_clean_sheet"] is not None and b_def["freq_clean_sheet"] <= SEUIL_BAS:
        dims.append(("faible_clean_sheet_exterieur", b_def["freq_clean_sheet"]))
    if len(dims) >= 2:
        _ajoute(signaux, "btts_oui", "favorable", dims, fiabilite)

    # --- BTTS non : au moins une défense solide ET l'attaque en face peu fournie ---
    dims = []
    if a_def["freq_clean_sheet"] is not None and a_def["freq_clean_sheet"] >= SEUIL_HAUT:
        dims.append(("forte_clean_sheet_domicile", a_def["freq_clean_sheet"]))
    if b_off["freq_marque_0"] is not None and b_off["freq_marque_0"] >= SEUIL_BAS:
        dims.append(("exterieur_freq_marque_0", b_off["freq_marque_0"]))
    if len(dims) >= 2:
        _ajoute(signaux, "btts_non", "favorable", dims, fiabilite)

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
    if len(coeur) >= 1 and len(coeur) + len(soutien) >= 2:
        _ajoute(signaux, "over_2_5", "favorable", coeur + soutien, fiabilite)

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
    if len(coeur) >= 1 and len(coeur) + len(soutien) >= 2:
        _ajoute(signaux, "under_2_5", "favorable", coeur + soutien, fiabilite)

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
        _ajoute(signaux, "resultat_domicile", "favorable", dims, fiabilite)

    signaux.sort(key=lambda s: s["nb_dimensions_convergentes"], reverse=True)
    return signaux
