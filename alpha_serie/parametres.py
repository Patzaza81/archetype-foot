"""Paramètres du moteur alpha « séries » (nouvelle logique de Patrick).

Deux sortes de valeurs, séparées :
- RÈGLES DE PATRICK (constantes de la méthode, jamais recalculées) : échantillon 4 à 7 matchs, coefficient k, « constante de 3 », cote minimale.
- PARAMÈTRES CALIBRÉS (marges de niveau, seuils d'écart attendu, seuil de branche) : les valeurs ci-dessous sont des PLANCHERS (valeurs de départ
  validées par Patrick) ; `calibration.py` les recalcule sur l'archive de test et ne peut que les ÉLARGIR, jamais les resserrer.
Le fichier `parametres.json` (écrit par `calibration.py`) prime sur ces valeurs par défaut.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

FICHIER = Path(__file__).with_name("parametres.json")

# --- Règles de Patrick (méthodologie sacrée) -------------------------------------------------------------------
MIN_MATCHS = 4                     # en dessous, le match est exclu de l'analyse
MAX_MATCHS = 7                     # fenêtre : 7 derniers matchs au même lieu
K_PAR_ECHANTILLON = {4: 0.8, 5: 0.9}   # 6 matchs et plus : 1,0 (selon le plus petit échantillon des deux équipes)
K_DEFAUT = 1.0
CONSTANTE_MULTISCORE = 3           # un groupe de scores « revient dans une constante de 3 » : au moins 3 scénarios sur l'ensemble des deux branches
COTE_MIN = 1.25                    # étape 2 seulement ; pas de cote maximale ; aucune limite de cote pour les multiscores


def coef_k(n: int) -> float | None:
    """None si l'échantillon est insuffisant (match exclu)."""
    if n < MIN_MATCHS:
        return None
    return K_PAR_ECHANTILLON.get(n, K_DEFAUT)


# --- Valeurs de départ (planchers) -----------------------------------------------------------------------------
DEFAUT = {
    "seuil_branche": 0.5,          # part minimale de scénarios validants dans CHAQUE branche (offensive et défensive)
    # Marge de niveau, en buts : « plus de L » exige attendu >= L + marge ; « moins de L » exige attendu <= L - marge.
    "marges": {
        "defaut": 1.0,
        "total_plus": {"1.5": 2.0, "2.5": 1.0, "3.5": 1.0, "4.5": 1.0},
        "total_moins": {"1.5": 1.0, "2.5": 1.0, "3.5": 1.5, "4.5": 1.0},
        "equipe_plus": {"0.5": 1.5, "1.5": 1.0, "2.5": 1.0},
        "equipe_moins": {"0.5": 1.0, "1.5": 1.0, "2.5": 1.0},
        "handicap_1_5": 1.0,
    },
    # Écart attendu d = buts attendus domicile - buts attendus extérieur.
    "seuils_resultat": {
        "dom_gagne": 0.5,          # victoire domicile : d >= seuil
        "ext_gagne": 0.5,          # victoire extérieur : d <= -seuil
        "dom_ne_perd_pas": 1.0,    # 1N et handicap +0,5 domicile : d >= seuil
        "ext_ne_perd_pas": 0.5,    # N2 et handicap +0,5 extérieur : d <= -seuil
        "nul": None,               # match nul : |d| <= seuil ; None = aucun seuil appris (le nul est alors rejeté au registre, avec la raison)
    },
    "multigoals": {
        "marge_borne": 1.0,        # le total attendu doit rester à au moins cette distance de chaque borne de la fourchette
        "plages": [[1, 2], [1, 3], [1, 4], [2, 3], [2, 4], [2, 5], [3, 4], [3, 5], [3, 6]],
    },
    "provisoire": [],
    "source": "valeurs de départ (aucune calibration)",
}


def defaut() -> dict:
    return copy.deepcopy(DEFAUT)


def charger(fichier: Path | None = None) -> dict:
    f = fichier or FICHIER
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return defaut()


def ecrire(params: dict, fichier: Path | None = None) -> None:
    (fichier or FICHIER).write_text(json.dumps(params, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
