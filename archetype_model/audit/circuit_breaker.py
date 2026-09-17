"""
archetype_model/audit/circuit_breaker.py — Disjoncteur d'intégrité des
données brutes (chantier Patrick, 17/09/2026, module d'audit passif).

RÔLE UNIQUE : observer et taguer la qualité des données d'UN match AVANT
qu'il n'entre dans le Péage 1 (matrice_croisement, voir main.py) -- ne
rejette JAMAIS un match lui-même, ne modifie AUCUN seuil de production.
Le verdict produit est une information ADDITIVE, consommée en aval par
telemetry.py/report.py, jamais par la logique de décision elle-même.
Conforme à la règle stricte de Patrick (17/09/2026) : "SANS JAMAIS
modifier dynamiquement les règles ni les seuils fixes de l'entonnoir".

Trois motifs de dégradation, indépendants (un match peut cumuler
plusieurs motifs à la fois) :

1. ECHANTILLON_INSUFFISANT (par rôle domicile/extérieur) :
   n_brut < N_MIN_ECHANTILLON (5). Ce seuil est un DOUBLON VOLONTAIRE de
   data.validation.N_MIN_UTILISABLE (déjà appliqué en amont -- le match
   ne serait de toute façon jamais éligible). Il n'est PAS importé
   directement depuis validation.py pour ne créer aucun couplage entre
   ce module d'audit et le moteur de décision : si N_MIN_UTILISABLE
   change un jour, ce fichier doit être mis à jour EXPLICITEMENT par un
   humain, jamais silencieusement par un import partagé. Ce motif ne
   fait que RE-EXPOSER un fait déjà décidé ailleurs, pour le dashboard.

2. TAUX_DONNEES_MANQUANTES_ELEVE (par rôle) : plus de 15 % des matchs
   bruts trouvés pour l'équipe ont été rejetés par
   data.validation/l'extraction (score illisible, ligne malformée,
   etc.). Proxy : 1 - (n_utilisable / n_brut), lu directement sur le
   dict déjà produit par data.validation.classifie_fenetre -- aucun
   recalcul, aucune requête réseau supplémentaire.

3. VARIATION_COTE_BRUTALE (par marché) : la cote observée au moment du
   scan diffère de plus de 15 % du premier relevé jamais enregistré pour
   ce même (match, marché), persisté dans un fichier de snapshots
   horodatés. CE N'EST PAS une vraie cote d'ouverture bookmaker --
   aucune donnée de ce projet ne capture l'ouverture réelle aujourd'hui.
   Le tout premier scan d'un (match, marché) n'a rien à comparer : il
   enregistre son relevé et ne peut jamais déclencher ce motif ce
   soir-là. Le signal ne devient utile qu'après plusieurs scans/nuits
   successifs sur le même match (fenêtre J0-J+3).

AUCUNE fonction de ce fichier n'écrit dans data/validation.py,
convergence.py, ni dans le catalogue de signaux/candidats lui-même.
"""

from __future__ import annotations

import datetime
import json
import os
from typing import Any, Mapping, Optional

FICHIER_SNAPSHOTS_COTES_DEFAUT = "data/audit_odds_snapshots.json"

# Seuils propres à CE module d'audit -- distincts et sans lien de code
# avec les seuils de production (SEUIL_PEAGE1, COTE_MIN/MAX, EDV_MIN_*).
# Modifier ces valeurs n'a AUCUN effet sur la sélection P1/P2/P3.
SEUIL_TAUX_MANQUANT = 0.15
SEUIL_VARIATION_COTE = 0.15
N_MIN_ECHANTILLON = 5  # doublon documentaire de data.validation.N_MIN_UTILISABLE (voir docstring)

MOTIF_ECHANTILLON_INSUFFISANT = "ECHANTILLON_INSUFFISANT"
MOTIF_TAUX_MANQUANT_ELEVE = "TAUX_DONNEES_MANQUANTES_ELEVE"
MOTIF_VARIATION_COTE = "VARIATION_COTE_BRUTALE"

STATUT_OK = "OK"
STATUT_DATA_CORRUPTED = "DATA_CORRUPTED"
STATUT_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

# Priorité de statut quand plusieurs motifs coexistent : une donnée
# corrompue (taux manquant élevé ou cote incohérente) est un signal plus
# grave qu'un simple échantillon petit mais propre -- DATA_CORRUPTED
# l'emporte toujours sur INSUFFICIENT_DATA si les deux sont présents.
_MOTIFS_CORRUPTION = frozenset({MOTIF_TAUX_MANQUANT_ELEVE, MOTIF_VARIATION_COTE})
_MOTIFS_INSUFFISANCE = frozenset({MOTIF_ECHANTILLON_INSUFFISANT})


def _taux_donnees_manquantes(fenetre: Mapping[str, Any]) -> Optional[float]:
    """1 - (n_utilisable / n_brut). None si n_brut vaut 0 (rien à
    mesurer -- pas une valeur inventée)."""
    n_brut = fenetre.get("n_brut", 0) or 0
    if n_brut <= 0:
        return None
    n_utilisable = len(fenetre.get("matchs_retenus") or [])
    return 1.0 - (n_utilisable / n_brut)


def _evalue_role(fenetre: Mapping[str, Any], role: str) -> list[dict[str, Any]]:
    motifs: list[dict[str, Any]] = []
    n_brut = fenetre.get("n_brut", 0) or 0

    if n_brut < N_MIN_ECHANTILLON:
        motifs.append({
            "motif": MOTIF_ECHANTILLON_INSUFFISANT,
            "role": role,
            "n_brut": n_brut,
            "seuil": N_MIN_ECHANTILLON,
        })

    taux = _taux_donnees_manquantes(fenetre)
    if taux is not None:
        # Arrondi AVANT comparaison, pas seulement à l'affichage : une
        # fraction "propre" (ex. 17/20 = 15% pile) peut retomber à
        # 0.15000000000000002 en flottant IEEE-754 et franchirait le
        # seuil par erreur d'arrondi, jamais par un vrai écart de
        # données -- round() à 4 décimales élimine ce faux positif sans
        # perdre de précision utile (0.01% n'a aucun sens métier ici).
        taux_arrondi = round(taux, 4)
        if taux_arrondi > SEUIL_TAUX_MANQUANT:
            motifs.append({
                "motif": MOTIF_TAUX_MANQUANT_ELEVE,
                "role": role,
                "taux": taux_arrondi,
                "seuil": SEUIL_TAUX_MANQUANT,
            })

    return motifs


def _charge_snapshots(fichier: str) -> dict[str, Any]:
    if not os.path.exists(fichier):
        return {}
    try:
        with open(fichier, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _sauve_snapshots(cache: Mapping[str, Any], fichier: str) -> None:
    dossier = os.path.dirname(fichier)
    if dossier:
        os.makedirs(dossier, exist_ok=True)
    with open(fichier, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _cle_snapshot(match_id: str, marche: str) -> str:
    return f"{match_id}||{marche}"


def _normalise_marche(cle_cote: Any) -> str:
    """Convertit une clé de cote (tuple type ('1x2','domicile') ou
    ('over_under_total', 2.5, 'over')) en identifiant de marché stable
    pour la clé de snapshot. Accepte aussi une simple chaîne."""
    if isinstance(cle_cote, tuple):
        return "|".join(str(p) for p in cle_cote)
    return str(cle_cote)


def verifie_variation_cote(
    match_id: str,
    marche: Any,
    cote_actuelle: Optional[float],
    fichier_snapshots: str = FICHIER_SNAPSHOTS_COTES_DEFAUT,
) -> Optional[dict[str, Any]]:
    """Compare `cote_actuelle` au premier relevé jamais enregistré pour
    (match_id, marche). Enregistre le relevé s'il s'agit du premier --
    ne peut alors jamais détecter de variation ce soir-là, rien à
    comparer. Retourne un dict motif si l'écart relatif dépasse
    SEUIL_VARIATION_COTE, sinon None.

    `cote_actuelle` invalide (None ou <= 0) : ignoré sans aucun
    enregistrement -- jamais une fausse valeur de référence persistée.
    """
    if cote_actuelle is None or cote_actuelle <= 0:
        return None

    cle_marche = _normalise_marche(marche)
    cache = _charge_snapshots(fichier_snapshots)
    cle = _cle_snapshot(match_id, cle_marche)
    entree = cache.get(cle)

    if entree is None:
        cache[cle] = {
            "cote_premiere_vue": cote_actuelle,
            "horodatage": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        _sauve_snapshots(cache, fichier_snapshots)
        return None

    cote_reference = entree.get("cote_premiere_vue")
    if not cote_reference or cote_reference <= 0:
        return None

    variation = abs(cote_actuelle - cote_reference) / cote_reference
    if variation > SEUIL_VARIATION_COTE:
        return {
            "motif": MOTIF_VARIATION_COTE,
            "marche": cle_marche,
            "cote_premiere_vue": cote_reference,
            "cote_actuelle": cote_actuelle,
            "variation": round(variation, 4),
            "seuil": SEUIL_VARIATION_COTE,
        }
    return None


def evalue_integrite(
    fenetre_domicile: Mapping[str, Any],
    fenetre_exterieur: Mapping[str, Any],
    match_id: Optional[str] = None,
    cotes: Optional[Mapping[Any, float]] = None,
    fichier_snapshots: str = FICHIER_SNAPSHOTS_COTES_DEFAUT,
) -> dict[str, Any]:
    """Verdict d'intégrité PASSIF pour un match, calculé avant le
    Péage 1. Ne rejette rien -- retourne {"statut", "motifs"} pour
    consommation en aval (télémétrie, dashboard).

    `cotes` optionnel : dict {cle_cote: valeur}, comparé marché par
    marché SI `match_id` est fourni (sans match_id, aucune persistance
    n'est possible -- la vérification de variation est alors ignorée,
    jamais devinée).
    """
    motifs: list[dict[str, Any]] = []
    motifs += _evalue_role(fenetre_domicile, "domicile")
    motifs += _evalue_role(fenetre_exterieur, "exterieur")

    if match_id and cotes:
        for cle_cote, valeur in cotes.items():
            motif = verifie_variation_cote(match_id, cle_cote, valeur, fichier_snapshots)
            if motif:
                motifs.append(motif)

    motifs_presents = {m["motif"] for m in motifs}
    if motifs_presents & _MOTIFS_CORRUPTION:
        statut = STATUT_DATA_CORRUPTED
    elif motifs_presents & _MOTIFS_INSUFFISANCE:
        statut = STATUT_INSUFFICIENT_DATA
    else:
        statut = STATUT_OK

    return {"statut": statut, "motifs": motifs}
