"""
archetype_model/signals/matrice_croisement.py
=============================================
Matrice de croisement des profils qualitatifs domicile / extérieur.

PRINCIPE :
    1. profil_equipe.construit_profil() — valeur réelle de chaque
       équipe SUR SON RÔLE.
    2. CE MODULE — croise les deux profils sur plusieurs dimensions
       indépendantes pour faire apparaître des TENDANCES NETTES avant
       tout calcul de lambda / EDV.
    3. lambda / EDV / robustesse (main.py, poisson/, edv/) arbitrent
       ENSUITE entre les tendances qui ressortent ici.

Invariants :
    - Zéro cote, zéro bookmaker.
    - Aucune décision finale : ne fait que produire des signaux bruts.
    - Le score_pondere est un produit simple nb_dimensions × poids_fiabilite.
"""

from __future__ import annotations

from typing import Any

from ..statistics.profil_equipe import (
    STATUT_FIABLE,
    LIGNES_OVER_UNDER_SUPPLEMENTAIRES,
    LIGNES_HANDICAP_PAR_DEFAUT,
)

SEUIL_HAUT = 0.60   # fréquence au-dessus de laquelle une tendance est "forte"
SEUIL_BAS = 0.40    # fréquence en-dessous de laquelle une tendance est "forte" inversée


# =============================================================
# FIABILITÉ CROISÉE
# =============================================================

def _niveau_fiabilite_croise(profil_a: dict, profil_b: dict) -> str:
    """
    Un croisement n'est fiable que si les DEUX profils le sont —
    la fiabilité d'une paire est celle du maillon le plus faible.
    """
    if (
        profil_a.get("statut_fiabilite") == STATUT_FIABLE
        and profil_b.get("statut_fiabilite") == STATUT_FIABLE
    ):
        return STATUT_FIABLE
    return "A_SURVEILLER"


def _poids_fiabilite_croise(profil_a: dict, profil_b: dict) -> float:
    """Maillon le plus faible."""
    return min(
        profil_a.get("poids_fiabilite", 0.0),
        profil_b.get("poids_fiabilite", 0.0),
    )


# =============================================================
# OUTIL D'AJOUT DE SIGNAL
# =============================================================

def _ajoute(
    signaux: list[dict],
    marche: str,
    direction: str,
    poids_dimensions: list[tuple[str, float]],
    fiabilite: str,
    poids_fiabilite_num: float,
):
    """Combine le nombre de dimensions convergentes et la fiabilité en un score_pondere unique."""
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


# =============================================================
# LIGNES OVER/UNDER (généralisation)
# =============================================================

def _ajoute_over_under_ligne(signaux, ligne, a_ou, b_ou, a_off, b_off, fiabilite, poids_num):
    """Généralise les règles over/under à une ligne arbitraire."""
    tag = str(ligne).replace(".", "_")

    # --- OVER
    coeur = []
    if a_ou["freq_over"] is not None and a_ou["freq_over"] >= SEUIL_HAUT:
        coeur.append((f"over_{tag}_domicile", a_ou["freq_over"]))
    if b_ou["freq_over"] is not None and b_ou["freq_over"] >= SEUIL_HAUT:
        coeur.append((f"over_{tag}_exterieur", b_ou["freq_over"]))
    soutien = []
    if a_off["freq_marque_1_plus"] is not None and a_off["freq_marque_1_plus"] >= SEUIL_HAUT:
        soutien.append(("attaque_domicile_active", a_off["freq_marque_1_plus"]))
    if b_off["freq_marque_1_plus"] is not None and b_off["freq_marque_1_plus"] >= SEUIL_HAUT:
        soutien.append(("attaque_exterieur_active", b_off["freq_marque_1_plus"]))
    if a_ou["serie_over_actuelle"] >= 2:
        soutien.append((f"serie_over_{tag}_domicile", a_ou["serie_over_actuelle"]))
    if b_ou["serie_over_actuelle"] >= 2:
        soutien.append((f"serie_over_{tag}_exterieur", b_ou["serie_over_actuelle"]))
    if len(coeur) >= 1 and len(coeur) + len(soutien) >= 2:
        _ajoute(signaux, f"over_{tag}", "favorable", coeur + soutien, fiabilite, poids_num)

    # --- UNDER
    coeur = []
    if a_ou["freq_over"] is not None and a_ou["freq_over"] <= SEUIL_BAS:
        coeur.append((f"under_{tag}_domicile", a_ou["freq_under"]))
    if b_ou["freq_over"] is not None and b_ou["freq_over"] <= SEUIL_BAS:
        coeur.append((f"under_{tag}_exterieur", b_ou["freq_under"]))
    soutien = []
    if a_ou["serie_under_actuelle"] >= 2:
        soutien.append((f"serie_under_{tag}_domicile", a_ou["serie_under_actuelle"]))
    if b_ou["serie_under_actuelle"] >= 2:
        soutien.append((f"serie_under_{tag}_exterieur", b_ou["serie_under_actuelle"]))
    if len(coeur) >= 1 and len(coeur) + len(soutien) >= 2:
        _ajoute(signaux, f"under_{tag}", "favorable", coeur + soutien, fiabilite, poids_num)


# =============================================================
# LIGNES HANDICAP (généralisation)
# =============================================================

def _ajoute_handicap_ligne(signaux, ligne, a_hcp, b_hcp, fiabilite, poids_num):
    """Signal de croisement pour le Handicap 3 choix à `ligne`."""
    tag = str(ligne).replace(".", "_").replace("-", "m")

    # --- Domicile couvre
    coeur = []
    if a_hcp["freq_couvre"] is not None and a_hcp["freq_couvre"] >= SEUIL_HAUT:
        coeur.append((f"handicap_{tag}_domicile_couvre", a_hcp["freq_couvre"]))
    if b_hcp["freq_perd"] is not None and b_hcp["freq_perd"] >= SEUIL_HAUT:
        coeur.append((f"handicap_{tag}_exterieur_perd", b_hcp["freq_perd"]))
    soutien = []
    if a_hcp["serie_couvre_actuelle"] >= 2:
        soutien.append((f"serie_handicap_{tag}_domicile", a_hcp["serie_couvre_actuelle"]))
    if len(coeur) >= 1 and len(coeur) + len(soutien) >= 2:
        _ajoute(signaux, f"handicap_domicile_{tag}", "favorable", coeur + soutien, fiabilite, poids_num)

    # --- Extérieur couvre
    coeur = []
    if a_hcp["freq_perd"] is not None and a_hcp["freq_perd"] >= SEUIL_HAUT:
        coeur.append((f"handicap_{tag}_domicile_perd", a_hcp["freq_perd"]))
    if b_hcp["freq_couvre"] is not None and b_hcp["freq_couvre"] >= SEUIL_HAUT:
        coeur.append((f"handicap_{tag}_exterieur_couvre", b_hcp["freq_couvre"]))
    soutien = []
    if b_hcp["serie_couvre_actuelle"] >= 2:
        soutien.append((f"serie_handicap_{tag}_exterieur", b_hcp["serie_couvre_actuelle"]))
    if len(coeur) >= 1 and len(coeur) + len(soutien) >= 2:
        _ajoute(signaux, f"handicap_exterieur_{tag}", "favorable", coeur + soutien, fiabilite, poids_num)


# =============================================================
# FONCTION PRINCIPALE
# =============================================================

def croise_profils(
    profil_domicile: dict[str, Any],
    profil_exterieur: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Croise le profil domicile avec le profil extérieur.
    Retourne la liste des signaux triée par score_pondere décroissant.
    """
    fiabilite = _niveau_fiabilite_croise(profil_domicile, profil_exterieur)
    poids_num = _poids_fiabilite_croise(profil_domicile, profil_exterieur)
    signaux: list[dict] = []

    a_off = profil_domicile["attaque"]
    a_def = profil_domicile["defense"]
    a_res = profil_domicile["resultats"]
    a_bt = profil_domicile["tendances_buts"]

    b_off = profil_exterieur["attaque"]
    b_def = profil_exterieur["defense"]
    b_res = profil_exterieur["resultats"]
    b_bt = profil_exterieur["tendances_buts"]

    # ---------------------------------------------------------
    # Plus de buts équipe domicile
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # Plus de buts équipe extérieure
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # BTTS oui
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # BTTS non
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # Over 2.5
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # Under 2.5
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # Cage inviolée domicile
    # ---------------------------------------------------------
    coeur = []
    if b_off["freq_marque_0"] is not None and b_off["freq_marque_0"] >= SEUIL_HAUT:
        coeur.append(("exterieur_freq_marque_0_haute", b_off["freq_marque_0"]))
    if a_def["freq_clean_sheet"] is not None and a_def["freq_clean_sheet"] >= SEUIL_HAUT:
        coeur.append(("domicile_clean_sheet_haute", a_def["freq_clean_sheet"]))
    soutien = []
    if b_off["serie_sans_marquer_actuelle"] >= 2:
        soutien.append(("serie_sans_marquer_exterieur", b_off["serie_sans_marquer_actuelle"]))
    if a_def["serie_clean_sheet_actuelle"] >= 2:
        soutien.append(("serie_clean_sheet_domicile", a_def["serie_clean_sheet_actuelle"]))
    if len(coeur) >= 1 and len(coeur) + len(soutien) >= 2:
        _ajoute(signaux, "cage_inviolee_domicile", "favorable", coeur + soutien, fiabilite, poids_num)

    # ---------------------------------------------------------
    # Cage inviolée extérieur
    # ---------------------------------------------------------
    coeur = []
    if a_off["freq_marque_0"] is not None and a_off["freq_marque_0"] >= SEUIL_HAUT:
        coeur.append(("domicile_freq_marque_0_haute", a_off["freq_marque_0"]))
    if b_def["freq_clean_sheet"] is not None and b_def["freq_clean_sheet"] >= SEUIL_HAUT:
        coeur.append(("exterieur_clean_sheet_haute", b_def["freq_clean_sheet"]))
    soutien = []
    if a_off["serie_sans_marquer_actuelle"] >= 2:
        soutien.append(("serie_sans_marquer_domicile", a_off["serie_sans_marquer_actuelle"]))
    if b_def["serie_clean_sheet_actuelle"] >= 2:
        soutien.append(("serie_clean_sheet_exterieur", b_def["serie_clean_sheet_actuelle"]))
    if len(coeur) >= 1 and len(coeur) + len(soutien) >= 2:
        _ajoute(signaux, "cage_inviolee_exterieur", "favorable", coeur + soutien, fiabilite, poids_num)

    # ---------------------------------------------------------
    # Encaisse domicile
    # ---------------------------------------------------------
    coeur = []
    if b_off["freq_marque_1_plus"] is not None and b_off["freq_marque_1_plus"] >= SEUIL_HAUT:
        coeur.append(("exterieur_freq_marque_1plus_haute", b_off["freq_marque_1_plus"]))
    if a_def["freq_encaisse_2_plus"] is not None and a_def["freq_encaisse_2_plus"] >= SEUIL_BAS:
        coeur.append(("domicile_encaisse_frequent", a_def["freq_encaisse_2_plus"]))
    soutien = []
    if b_off["serie_marque_actuelle"] >= 2:
        soutien.append(("serie_marque_exterieur", b_off["serie_marque_actuelle"]))
    if a_def["serie_encaisse_actuelle"] >= 2:
        soutien.append(("serie_encaisse_domicile", a_def["serie_encaisse_actuelle"]))
    if len(coeur) >= 1 and len(coeur) + len(soutien) >= 2:
        _ajoute(signaux, "encaisse_domicile", "favorable", coeur + soutien, fiabilite, poids_num)

    # ---------------------------------------------------------
    # Encaisse extérieur
    # ---------------------------------------------------------
    coeur = []
    if a_off["freq_marque_1_plus"] is not None and a_off["freq_marque_1_plus"] >= SEUIL_HAUT:
        coeur.append(("domicile_freq_marque_1plus_haute", a_off["freq_marque_1_plus"]))
    if b_def["freq_encaisse_2_plus"] is not None and b_def["freq_encaisse_2_plus"] >= SEUIL_BAS:
        coeur.append(("exterieur_encaisse_frequent", b_def["freq_encaisse_2_plus"]))
    soutien = []
    if a_off["serie_marque_actuelle"] >= 2:
        soutien.append(("serie_marque_domicile", a_off["serie_marque_actuelle"]))
    if b_def["serie_encaisse_actuelle"] >= 2:
        soutien.append(("serie_encaisse_exterieur", b_def["serie_encaisse_actuelle"]))
    if len(coeur) >= 1 and len(coeur) + len(soutien) >= 2:
        _ajoute(signaux, "encaisse_exterieur", "favorable", coeur + soutien, fiabilite, poids_num)

    # ---------------------------------------------------------
    # Lignes Over/Under supplémentaires
    # ---------------------------------------------------------
    for ligne in LIGNES_OVER_UNDER_SUPPLEMENTAIRES:
        _ajoute_over_under_ligne(
            signaux, ligne,
            profil_domicile["tendances_over_under"][ligne],
            profil_exterieur["tendances_over_under"][ligne],
            a_off, b_off, fiabilite, poids_num,
        )

    # ---------------------------------------------------------
    # Lignes Handicap 3 choix
    # ---------------------------------------------------------
    for ligne in LIGNES_HANDICAP_PAR_DEFAUT:
        _ajoute_handicap_ligne(
            signaux, ligne,
            profil_domicile["tendances_handicap"][ligne],
            profil_exterieur["tendances_handicap"][ligne],
            fiabilite, poids_num,
        )

    # ---------------------------------------------------------
    # Domination nette domicile
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # Domination nette extérieur
    # ---------------------------------------------------------
    dims = []
    if b_res["forme_ponderee_recence"] is not None and b_res["forme_ponderee_recence"] >= 2.0:
        dims.append(("forme_recente_exterieur", b_res["forme_ponderee_recence"]))
    if a_res["forme_ponderee_recence"] is not None and a_res["forme_ponderee_recence"] <= 1.0:
        dims.append(("forme_recente_domicile_faible", a_res["forme_ponderee_recence"]))
    if b_res["freq_victoires"] is not None and b_res["freq_victoires"] >= SEUIL_HAUT:
        dims.append(("freq_victoires_exterieur", b_res["freq_victoires"]))
    if a_res["freq_defaites"] is not None and a_res["freq_defaites"] >= SEUIL_HAUT:
        dims.append(("freq_defaites_domicile", a_res["freq_defaites"]))
    if len(dims) >= 2:
        _ajoute(signaux, "resultat_exterieur", "favorable", dims, fiabilite, poids_num)

    # ---------------------------------------------------------
    # Signal Résultat Nul
    # ---------------------------------------------------------
    coeur = []
    if a_res.get("freq_nuls") is not None and a_res["freq_nuls"] >= 0.25:
        coeur.append(("freq_nuls_domicile", a_res["freq_nuls"]))
    if b_res.get("freq_nuls") is not None and b_res["freq_nuls"] >= 0.25:
        coeur.append(("freq_nuls_exterieur", b_res["freq_nuls"]))
    soutien = []
    if a_bt.get("freq_over_2_5") is not None and a_bt["freq_over_2_5"] <= SEUIL_BAS:
        soutien.append(("under_2.5_domicile_propice_nul", 1 - a_bt["freq_over_2_5"]))
    if b_bt.get("freq_over_2_5") is not None and b_bt["freq_over_2_5"] <= SEUIL_BAS:
        soutien.append(("under_2.5_exterieur_propice_nul", 1 - b_bt["freq_over_2_5"]))
    if (
        a_res.get("forme_ponderee_recence") is not None
        and b_res.get("forme_ponderee_recence") is not None
        and abs(a_res["forme_ponderee_recence"] - b_res["forme_ponderee_recence"]) <= 0.5
    ):
        soutien.append((
            "equilibre_forme_recente",
            abs(a_res["forme_ponderee_recence"] - b_res["forme_ponderee_recence"]),
        ))
    if len(coeur) >= 1 and len(coeur) + len(soutien) >= 2:
        _ajoute(signaux, "resultat_nul", "favorable", coeur + soutien, fiabilite, poids_num)

    # ---------------------------------------------------------
    # Résolution des contradictions
    # ---------------------------------------------------------
    opposes = {
        "over_2_5": "under_2_5", "under_2_5": "over_2_5",
        "btts_oui": "btts_non", "btts_non": "btts_oui",
        "buts_equipe_domicile_plus": "buts_equipe_exterieur_plus",
        "buts_equipe_exterieur_plus": "buts_equipe_domicile_plus",
        "cage_inviolee_domicile": "encaisse_domicile",
        "encaisse_domicile": "cage_inviolee_domicile",
        "cage_inviolee_exterieur": "encaisse_exterieur",
        "encaisse_exterieur": "cage_inviolee_exterieur",
        "resultat_domicile": "resultat_exterieur",
        "resultat_exterieur": "resultat_domicile",
    }
    for ligne in LIGNES_OVER_UNDER_SUPPLEMENTAIRES:
        tag = str(ligne).replace(".", "_")
        opposes[f"over_{tag}"] = f"under_{tag}"
        opposes[f"under_{tag}"] = f"over_{tag}"
    for ligne in LIGNES_HANDICAP_PAR_DEFAUT:
        tag = str(ligne).replace(".", "_").replace("-", "m")
        opposes[f"handicap_domicile_{tag}"] = f"handicap_exterieur_{tag}"
        opposes[f"handicap_exterieur_{tag}"] = f"handicap_domicile_{tag}"

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