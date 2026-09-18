"""
archetype_model/statistics/profil_equipe.py
===========================================
Module de profilage statistique d'équipe — Péage 1 (version 2.5).

Rôle :
    - Calculer les fréquences brutes et effectives d'une équipe sur son
      rôle du jour (domicile ou extérieur) pour alimenter le Péage 1.
    - Exposer les volumes bruts pour le Péage 2 (peage_2.py).
    - Exposer les blocs structurés attendus par matrice_croisement.py.

Invariants :
    - Zéro cote, zéro bookmaker.
    - Pas de handicap joué ici (calcul de fréquence uniquement).
    - Pas de H2H.
    - Pas de tri des matchs (contrat amont : ancien -> récent).
    - Pas de décision finale.

CORRECTIF 18/09/2026 (v2.5) : normalisation du format des matchs.
    Le loader (archetype_model/data/loader.py) fournit des dicts sous la
    forme {"domicile": bool, "buts_marques": int, "buts_encaisses": int}.
    Le reste du projet (peage_2.py, matrice_croisement.py, main.py) lit
    "gf" et "ga". Sans normalisation, tous les matchs étaient rejetés
    par _extraire_buts et P1 ne produisait aucun profil exploitable.
    La normalisation accepte les DEUX formats : "gf"/"ga" prioritaires,
    sinon "buts_marques"/"buts_encaisses". Aucun original n'est muté.
"""

from __future__ import annotations

from typing import Dict, Any, List, Tuple, Optional


# =============================================================
# CONFIGURATION
# =============================================================

SEUIL_STABILITE = 5
K_STABILISATION = 3.0
SEUIL_P1 = 0.40

LIEUX_VALIDES = frozenset({"domicile", "exterieur"})

FENETRE_SPEC_DEFAUT = 8
FENETRE_STAB_DEFAUT = 5

STATUT_FIABLE = "FIABLE"
STATUT_A_SURVEILLER = "A_SURVEILLER"

LIGNES_OVER_UNDER_SUPPLEMENTAIRES: Tuple[float, ...] = (1.5, 3.5)
LIGNES_HANDICAP_PAR_DEFAUT: Tuple[float, ...] = (-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5)

MARCHES_CIBLES: Tuple[str, ...] = (
    "victoire", "nul", "defaite",
    "over_0_5", "over_1_5", "over_2_5", "over_3_5",
    "under_0_5", "under_1_5", "under_2_5", "under_3_5",
    "btts_oui", "btts_non",
    "buts_marques_over_0_5", "buts_marques_over_1_5", "buts_marques_over_2_5",
    "buts_marques_under_0_5", "buts_marques_under_1_5", "buts_marques_under_2_5",
    "buts_encaisses_over_0_5", "buts_encaisses_over_1_5", "buts_encaisses_over_2_5",
    "buts_encaisses_under_0_5", "buts_encaisses_under_1_5", "buts_encaisses_under_2_5",
    "clean_sheet", "encaisse_au_moins_1",
)

GRILLE_CN = {
    1: 0.35,
    2: 0.60,
    3: 0.60,
    4: 0.75,
    5: 0.75,
    6: 0.90,
    7: 0.90,
    8: 0.90,
}


# =============================================================
# COEFFICIENT DE CONFIANCE
# =============================================================

def get_coefficient_cn(n: int) -> float:
    if n <= 0:
        return 0.0
    if n >= 9:
        return 1.00
    return GRILLE_CN[n]


# =============================================================
# VALIDATION BAS NIVEAU
# =============================================================

def _est_entier_positif(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _normalise_match(m: Any) -> Any:
    """
    Accepte les DEUX conventions du projet :
      - "gf" / "ga"                        (convention interne moteur)
      - "buts_marques" / "buts_encaisses"  (convention loader)

    Retourne un dict copié avec les clés "gf"/"ga" renseignées si elles
    manquaient. Ne modifie JAMAIS l'original. Un match sans aucune des
    deux conventions est retourné tel quel (sera rejeté par _extraire_buts).
    """
    if not isinstance(m, dict):
        return m
    if _est_entier_positif(m.get("gf")) and _est_entier_positif(m.get("ga")):
        return m
    fm = m.get("buts_marques")
    fa = m.get("buts_encaisses")
    if _est_entier_positif(fm) and _est_entier_positif(fa):
        copie = dict(m)
        copie["gf"] = fm
        copie["ga"] = fa
        return copie
    return m


def _extraire_buts(match: Dict[str, Any]) -> Optional[Tuple[int, int]]:
    if not isinstance(match, dict):
        return None
    gf = match.get("gf")
    ga = match.get("ga")
    if _est_entier_positif(gf) and _est_entier_positif(ga):
        return gf, ga
    return None


def _lieu_match(match: Dict[str, Any]) -> Optional[str]:
    if not isinstance(match, dict):
        return None
    lieu = match.get("lieu")
    if lieu in LIEUX_VALIDES:
        return lieu
    dom = match.get("domicile")
    if dom is True:
        return "domicile"
    if dom is False:
        return "exterieur"
    return None


def valider_matchs(historique: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    valides: List[Dict[str, Any]] = []
    for m in historique:
        if _extraire_buts(m) is not None:
            valides.append(m)
    return valides


# =============================================================
# SÉRIES
# =============================================================

def _serie_actuelle(matchs: List[Dict[str, Any]], condition) -> int:
    count = 0
    for m in reversed(matchs):
        b = _extraire_buts(m)
        if b is None:
            break
        if condition(b[0], b[1]):
            count += 1
        else:
            break
    return count


# =============================================================
# FRÉQUENCES BRUTES (à plat, compat P2)
# =============================================================

def calculer_frequences_brutes(matchs: List[Dict[str, Any]]) -> Dict[str, float]:
    if not matchs:
        return {m: 0.0 for m in MARCHES_CIBLES}

    n = len(matchs)
    compteurs = {m: 0 for m in MARCHES_CIBLES}

    for m in matchs:
        gf, ga = m["gf"], m["ga"]
        total = gf + ga

        if gf > ga: compteurs["victoire"] += 1
        elif gf == ga: compteurs["nul"] += 1
        else: compteurs["defaite"] += 1

        if total > 0.5: compteurs["over_0_5"] += 1
        if total > 1.5: compteurs["over_1_5"] += 1
        if total > 2.5: compteurs["over_2_5"] += 1
        if total > 3.5: compteurs["over_3_5"] += 1
        if total < 0.5: compteurs["under_0_5"] += 1
        if total < 1.5: compteurs["under_1_5"] += 1
        if total < 2.5: compteurs["under_2_5"] += 1
        if total < 3.5: compteurs["under_3_5"] += 1

        if gf > 0 and ga > 0: compteurs["btts_oui"] += 1
        else: compteurs["btts_non"] += 1

        if gf > 0.5: compteurs["buts_marques_over_0_5"] += 1
        if gf > 1.5: compteurs["buts_marques_over_1_5"] += 1
        if gf > 2.5: compteurs["buts_marques_over_2_5"] += 1
        if gf < 0.5: compteurs["buts_marques_under_0_5"] += 1
        if gf < 1.5: compteurs["buts_marques_under_1_5"] += 1
        if gf < 2.5: compteurs["buts_marques_under_2_5"] += 1

        if ga > 0.5: compteurs["buts_encaisses_over_0_5"] += 1
        if ga > 1.5: compteurs["buts_encaisses_over_1_5"] += 1
        if ga > 2.5: compteurs["buts_encaisses_over_2_5"] += 1
        if ga < 0.5: compteurs["buts_encaisses_under_0_5"] += 1
        if ga < 1.5: compteurs["buts_encaisses_under_1_5"] += 1
        if ga < 2.5: compteurs["buts_encaisses_under_2_5"] += 1

        if ga == 0: compteurs["clean_sheet"] += 1
        else: compteurs["encaisse_au_moins_1"] += 1

    return {m: round(c / n, 4) for m, c in compteurs.items()}


# =============================================================
# BLOCS STRUCTURÉS (compat matrice_croisement)
# =============================================================

def _calcule_bloc_attaque(matchs: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(matchs)
    if n == 0:
        return {
            "freq_marque_0": None, "freq_marque_1_plus": None,
            "freq_marque_2_plus": None,
            "serie_marque_actuelle": 0, "serie_sans_marquer_actuelle": 0,
        }
    nb_0 = sum(1 for m in matchs if m["gf"] == 0)
    nb_1 = sum(1 for m in matchs if m["gf"] >= 1)
    nb_2 = sum(1 for m in matchs if m["gf"] >= 2)
    return {
        "freq_marque_0": round(nb_0 / n, 4),
        "freq_marque_1_plus": round(nb_1 / n, 4),
        "freq_marque_2_plus": round(nb_2 / n, 4),
        "serie_marque_actuelle": _serie_actuelle(matchs, lambda gf, ga: gf >= 1),
        "serie_sans_marquer_actuelle": _serie_actuelle(matchs, lambda gf, ga: gf == 0),
    }


def _calcule_bloc_defense(matchs: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(matchs)
    if n == 0:
        return {
            "freq_clean_sheet": None, "freq_encaisse_2_plus": None,
            "serie_clean_sheet_actuelle": 0, "serie_encaisse_actuelle": 0,
        }
    nb_cs = sum(1 for m in matchs if m["ga"] == 0)
    nb_2 = sum(1 for m in matchs if m["ga"] >= 2)
    return {
        "freq_clean_sheet": round(nb_cs / n, 4),
        "freq_encaisse_2_plus": round(nb_2 / n, 4),
        "serie_clean_sheet_actuelle": _serie_actuelle(matchs, lambda gf, ga: ga == 0),
        "serie_encaisse_actuelle": _serie_actuelle(matchs, lambda gf, ga: ga >= 1),
    }


def _calcule_bloc_resultats(matchs: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(matchs)
    if n == 0:
        return {
            "freq_victoires": None, "freq_nuls": None, "freq_defaites": None,
            "marge_buts_moyenne": None, "forme_ponderee_recence": None,
        }
    victoires = sum(1 for m in matchs if m["gf"] > m["ga"])
    nuls = sum(1 for m in matchs if m["gf"] == m["ga"])
    defaites = sum(1 for m in matchs if m["gf"] < m["ga"])
    marge = sum(m["gf"] - m["ga"] for m in matchs) / n

    numerateur = 0.0
    denominateur = 0.0
    for i, m in enumerate(matchs):
        poids = i + 1
        if m["gf"] > m["ga"]:
            pts = 3.0
        elif m["gf"] == m["ga"]:
            pts = 1.0
        else:
            pts = 0.0
        numerateur += pts * poids
        denominateur += poids
    forme = numerateur / denominateur if denominateur > 0 else None

    return {
        "freq_victoires": round(victoires / n, 4),
        "freq_nuls": round(nuls / n, 4),
        "freq_defaites": round(defaites / n, 4),
        "marge_buts_moyenne": round(marge, 4),
        "forme_ponderee_recence": round(forme, 4) if forme is not None else None,
    }


def _calcule_bloc_tendances_buts(matchs: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(matchs)
    if n == 0:
        return {
            "freq_btts": None, "freq_over_2_5": None,
            "serie_btts_oui_actuelle": 0, "serie_btts_non_actuelle": 0,
            "serie_over_2_5_actuelle": 0, "serie_under_2_5_actuelle": 0,
        }
    nb_btts = sum(1 for m in matchs if m["gf"] > 0 and m["ga"] > 0)
    nb_over25 = sum(1 for m in matchs if (m["gf"] + m["ga"]) > 2.5)
    return {
        "freq_btts": round(nb_btts / n, 4),
        "freq_over_2_5": round(nb_over25 / n, 4),
        "serie_btts_oui_actuelle": _serie_actuelle(matchs, lambda gf, ga: gf > 0 and ga > 0),
        "serie_btts_non_actuelle": _serie_actuelle(matchs, lambda gf, ga: gf == 0 or ga == 0),
        "serie_over_2_5_actuelle": _serie_actuelle(matchs, lambda gf, ga: (gf + ga) > 2.5),
        "serie_under_2_5_actuelle": _serie_actuelle(matchs, lambda gf, ga: (gf + ga) < 2.5),
    }


def _calcule_bloc_tendances_over_under(
    matchs: List[Dict[str, Any]],
    lignes: Tuple[float, ...],
) -> Dict[float, Dict[str, Any]]:
    n = len(matchs)
    bloc: Dict[float, Dict[str, Any]] = {}
    for ligne in lignes:
        if n == 0:
            bloc[ligne] = {
                "freq_over": None, "freq_under": None,
                "serie_over_actuelle": 0, "serie_under_actuelle": 0,
            }
            continue
        nb_over = sum(1 for m in matchs if (m["gf"] + m["ga"]) > ligne)
        nb_under = sum(1 for m in matchs if (m["gf"] + m["ga"]) < ligne)
        bloc[ligne] = {
            "freq_over": round(nb_over / n, 4),
            "freq_under": round(nb_under / n, 4),
            "serie_over_actuelle": _serie_actuelle(matchs, lambda gf, ga, l=ligne: (gf + ga) > l),
            "serie_under_actuelle": _serie_actuelle(matchs, lambda gf, ga, l=ligne: (gf + ga) < l),
        }
    return bloc


def _calcule_bloc_tendances_handicap(
    matchs: List[Dict[str, Any]],
    lignes: Tuple[float, ...],
) -> Dict[float, Dict[str, Any]]:
    n = len(matchs)
    bloc: Dict[float, Dict[str, Any]] = {}
    for ligne in lignes:
        if n == 0:
            bloc[ligne] = {
                "freq_couvre": None, "freq_perd": None,
                "serie_couvre_actuelle": 0,
            }
            continue
        nb_couvre = sum(1 for m in matchs if (m["gf"] + ligne) > m["ga"])
        nb_perd = sum(1 for m in matchs if (m["gf"] + ligne) < m["ga"])
        bloc[ligne] = {
            "freq_couvre": round(nb_couvre / n, 4),
            "freq_perd": round(nb_perd / n, 4),
            "serie_couvre_actuelle": _serie_actuelle(matchs, lambda gf, ga, l=ligne: (gf + l) > ga),
        }
    return bloc


# =============================================================
# RÉGIME ET FIABILITÉ
# =============================================================

def _determiner_regime(n_spec_valides: int) -> str:
    if n_spec_valides == 0:
        return "indisponible"
    if n_spec_valides >= SEUIL_STABILITE:
        return "specifique_pur"
    return "mix_stabilise"


def _determiner_niveau_fiabilite(regime: str) -> str:
    return {
        "specifique_pur": "haute",
        "mix_stabilise": "stabilisee",
        "indisponible": "indisponible",
    }[regime]


def _poids_stabilisation(n_spec: int, k: float = K_STABILISATION) -> float:
    if n_spec <= 0:
        return 0.0
    return n_spec / (n_spec + k)


def _statut_fiabilite_depuis_cn(c_n: float) -> str:
    if c_n >= 0.75:
        return STATUT_FIABLE
    return STATUT_A_SURVEILLER


# =============================================================
# FILTRAGE HISTORIQUE
# =============================================================

def filtrer_historique_recent(
    historique_matchs: List[Dict[str, Any]],
    lieu_cible: Optional[str] = None,
    lieu_exclu: Optional[str] = None,
    fenetre: int = FENETRE_SPEC_DEFAUT,
    deja_vus: Optional[set] = None,
) -> List[Dict[str, Any]]:
    if lieu_cible is not None and lieu_cible not in LIEUX_VALIDES:
        raise ValueError(f"lieu_cible invalide : {lieu_cible!r}")
    if lieu_exclu is not None and lieu_exclu not in LIEUX_VALIDES:
        raise ValueError(f"lieu_exclu invalide : {lieu_exclu!r}")
    if fenetre <= 0:
        return []

    vus = deja_vus or set()
    resultat: List[Dict[str, Any]] = []

    for match in historique_matchs:
        if not isinstance(match, dict):
            continue
        lieu = _lieu_match(match)
        if lieu_cible is not None and lieu != lieu_cible:
            continue
        if lieu_exclu is not None and lieu == lieu_exclu:
            continue
        if id(match) in vus:
            continue
        resultat.append(match)
        if len(resultat) >= fenetre:
            break

    return resultat


# =============================================================
# CONSTRUCTION DU PROFIL
# =============================================================

def construit_profil(
    nom_equipe: str,
    historique_global: List[Dict[str, Any]],
    lieu: str,
    fenetre_specifique: int = FENETRE_SPEC_DEFAUT,
    fenetre_stabilisateur: int = FENETRE_STAB_DEFAUT,
    k_stabilisation: float = K_STABILISATION,
) -> Dict[str, Any]:
    """
    Construit le profil complet d'une équipe pour son rôle du jour.

    Contrat d'entrée :
        - historique_global trié du PLUS ANCIEN au PLUS RÉCENT.
        - lieu ∈ {"domicile", "exterieur"}.
        - chaque match : soit "gf"+"ga", soit
          "buts_marques"+"buts_encaisses", plus un marqueur de lieu
          ("lieu" en str ou "domicile" en bool).

    Sortie : dict à trois niveaux de compatibilité :
        - champs à plat : compat peage_2.py
        - bloc profil_role + disponibilite : compat main.py
        - blocs structurés : compat matrice_croisement.py
    """
    if lieu not in LIEUX_VALIDES:
        raise ValueError(f"lieu invalide : {lieu!r}. Attendu : {sorted(LIEUX_VALIDES)}")

    # ---- 0. Normalisation du format des matchs (gf/ga OU buts_marques/buts_encaisses)
    historique_global = [_normalise_match(m) for m in historique_global]

    # ---- 1. Échantillon spécifique (le rôle)
    matchs_specifiques = filtrer_historique_recent(
        historique_global,
        lieu_cible=lieu,
        fenetre=fenetre_specifique,
    )
    n_spec_brut = len(matchs_specifiques)

    # ---- 2. Échantillon stabilisateur (hors rôle, sans overlap)
    ids_specifiques = {id(m) for m in matchs_specifiques}
    matchs_stabilisateur = filtrer_historique_recent(
        historique_global,
        lieu_exclu=lieu,
        fenetre=fenetre_stabilisateur,
        deja_vus=ids_specifiques,
    )
    overlap_tolere = False
    if not matchs_stabilisateur:
        matchs_stabilisateur = filtrer_historique_recent(
            historique_global,
            lieu_cible=None,
            fenetre=fenetre_stabilisateur,
        )
        overlap_tolere = True
    n_stab_brut = len(matchs_stabilisateur)

    # ---- 3. Fréquences à plat (compat P2)
    matchs_specifiques_valides = valider_matchs(matchs_specifiques)
    n_spec_valides = len(matchs_specifiques_valides)
    freq_spec = calculer_frequences_brutes(matchs_specifiques_valides)

    matchs_stab_valides = valider_matchs(matchs_stabilisateur)
    n_stab_valides = len(matchs_stab_valides)
    freq_stab = calculer_frequences_brutes(matchs_stab_valides)

    # ---- 4. Volumes bruts (profil global)
    matchs_global_valides = valider_matchs(historique_global)
    n_global_valides = len(matchs_global_valides)
    total_gf_global = sum(m["gf"] for m in matchs_global_valides)
    total_ga_global = sum(m["ga"] for m in matchs_global_valides)
    moy_gf_global = round(total_gf_global / n_global_valides, 3) if n_global_valides else 0.0
    moy_ga_global = round(total_ga_global / n_global_valides, 3) if n_global_valides else 0.0

    # ---- 5. Régime et mélange
    regime = _determiner_regime(n_spec_valides)
    niveau = _determiner_niveau_fiabilite(regime)
    disponible = n_spec_valides > 0

    c_n = get_coefficient_cn(n_spec_valides)

    if regime == "specifique_pur":
        poids_spec = 1.0
        freq_finale = {k: round(freq_spec[k], 4) for k in MARCHES_CIBLES}
    elif regime == "mix_stabilise":
        poids_spec = _poids_stabilisation(n_spec_valides, k_stabilisation)
        freq_finale = {
            k: round(poids_spec * freq_spec[k] + (1 - poids_spec) * freq_stab[k], 4)
            for k in MARCHES_CIBLES
        }
    else:
        poids_spec = 0.0
        freq_finale = {k: round(freq_stab[k], 4) for k in MARCHES_CIBLES}

    # ---- 6. Fréquences effectives et marchés valides P1
    freq_effectives: Dict[str, float] = {}
    marches_valides_p1: Dict[str, bool] = {}
    for m in MARCHES_CIBLES:
        eff = round(freq_spec[m] * c_n, 4)
        freq_effectives[m] = eff
        marches_valides_p1[m] = eff >= SEUIL_P1

    a_un_marche_valide = any(marches_valides_p1.values())

    # ---- 7. Blocs structurés (compat matrice_croisement)
    blocs = matchs_specifiques_valides
    attaque = _calcule_bloc_attaque(blocs)
    defense = _calcule_bloc_defense(blocs)
    resultats = _calcule_bloc_resultats(blocs)
    tendances_buts = _calcule_bloc_tendances_buts(blocs)
    tendances_over_under = _calcule_bloc_tendances_over_under(blocs, (0.5, 1.5, 2.5, 3.5))
    tendances_handicap = _calcule_bloc_tendances_handicap(blocs, LIGNES_HANDICAP_PAR_DEFAUT)

    statut_fiabilite = _statut_fiabilite_depuis_cn(c_n)
    poids_fiabilite = 1.0 if statut_fiabilite == STATUT_FIABLE else 0.5

    # ---- 8. Assemblage
    return {
        # --- Identité
        "equipe": nom_equipe,
        "lieu_analyse": lieu,
        "role": lieu,  # alias rétrocompat

        # --- Signaux de disponibilité
        "disponible": disponible,
        "niveau_fiabilite": niveau,

        # --- Compat P2 (à plat)
        "echantillon_n": n_spec_valides,
        "volumes_bruts": {
            "total_gf": total_gf_global,
            "total_ga": total_ga_global,
            "moy_gf": moy_gf_global,
            "moy_ga": moy_ga_global,
        },
        "frequences_specifiques": freq_spec,
        "frequences_stabilisateur": freq_stab,
        "freq_finale": freq_finale,

        # --- Compat main.py
        "profil_role": {
            "n_valides": n_spec_valides,
            "c_n": c_n,
            "frequences_brutes": freq_spec,
            "frequences_effectives": freq_effectives,
            "marches_valides_p1": marches_valides_p1,
        },
        "disponibilite": {
            "a_des_donnees": disponible,
            "a_un_marche_valide": a_un_marche_valide,
        },
        "profil_global": {
            "n_valides": n_global_valides,
            "volumes_bruts": {
                "total_gf": total_gf_global,
                "total_ga": total_ga_global,
                "moy_gf": moy_gf_global,
                "moy_ga": moy_ga_global,
            },
        },

        # --- Compat matrice_croisement.py
        "attaque": attaque,
        "defense": defense,
        "resultats": resultats,
        "tendances_buts": tendances_buts,
        "tendances_over_under": tendances_over_under,
        "tendances_handicap": tendances_handicap,
        "statut_fiabilite": statut_fiabilite,
        "poids_fiabilite": poids_fiabilite,

        # --- Audit
        "audit": {
            "regime": regime,
            "seuil_stabilite": SEUIL_STABILITE,
            "specifique_n_brut": n_spec_brut,
            "specifique_n_valides": n_spec_valides,
            "stabilisateur_n_brut": n_stab_brut,
            "stabilisateur_n_valides": n_stab_valides,
            "overlap_tolere": overlap_tolere,
            "poids_specifique": round(poids_spec, 4),
            "poids_stabilisateur": round(1 - poids_spec, 4),
            "k_stabilisation": k_stabilisation,
            "version": "2.5",
        },
    }


# =============================================================
# HELPERS POUR L'AVAL
# =============================================================

def profil_est_consommable(profil: Dict[str, Any]) -> bool:
    return bool(profil.get("disponible", False))


def extraire_frequences_p1_validees(profil: Dict[str, Any]) -> Dict[str, float]:
    pr = profil.get("profil_role", {})
    freq_brutes = pr.get("frequences_brutes", {})
    marches_valides = pr.get("marches_valides_p1", {})
    return {
        marche: freq_brutes[marche]
        for marche, valide in marches_valides.items()
        if valide and marche in freq_brutes
    }


def resume_telemetrie(profil: Dict[str, Any]) -> Dict[str, Any]:
    audit = profil.get("audit", {})
    return {
        "equipe": profil.get("equipe"),
        "lieu": profil.get("lieu_analyse"),
        "disponible": profil.get("disponible", False),
        "niveau_fiabilite": profil.get("niveau_fiabilite", "indisponible"),
        "statut_fiabilite": profil.get("statut_fiabilite", STATUT_A_SURVEILLER),
        "regime": audit.get("regime", "indisponible"),
        "n_spec_valides": audit.get("specifique_n_valides", 0),
        "n_stab_valides": audit.get("stabilisateur_n_valides", 0),
        "poids_specifique": audit.get("poids_specifique", 0.0),
        "overlap_tolere": audit.get("overlap_tolere", False),
        "version": audit.get("version", "?"),
    }


# =============================================================
# EXEMPLE
# =============================================================

if __name__ == "__main__":
    import json

    # Test avec format loader : buts_marques / buts_encaisses
    historique_A = [
        {"domicile": True, "buts_marques": 2, "buts_encaisses": 1},
        {"domicile": False, "buts_marques": 1, "buts_encaisses": 1},
        {"domicile": True, "buts_marques": 3, "buts_encaisses": 0},
        {"domicile": True, "buts_marques": 1, "buts_encaisses": 2},
        {"domicile": False, "buts_marques": 0, "buts_encaisses": 0},
        {"domicile": True, "buts_marques": 2, "buts_encaisses": 2},
        {"domicile": True, "buts_marques": 1, "buts_encaisses": 0},
        {"domicile": False, "buts_marques": 2, "buts_encaisses": 3},
        {"domicile": True, "buts_marques": 0, "buts_encaisses": 1},
        {"domicile": True, "buts_marques": 4, "buts_encaisses": 1},
    ]

    profil = construit_profil("Équipe A", historique_A, lieu="domicile")
    print(json.dumps(profil, indent=2, ensure_ascii=False, default=str))