"""Paramètres du moteur alpha « séries » (nouvelle logique de Patrick).

Deux sortes de valeurs, séparées :
- RÈGLES DE PATRICK (constantes de la méthode, jamais recalculées) : échantillon 4 à 7 matchs, coefficient k, « constante de 3 », cote minimale.
- MARGES DES MARCHÉS DE BUTS : règle des buts entiers de Patrick (demi-but de marge : plus X,5 -> attendu >= X+1,5 ; moins X,5 -> attendu <= X+0,5), jamais recalculée.
- SEUILS D'ÉCART ATTENDU (victoire, ne perd pas) : aucun plancher fixé à la main ; `calibration.py` ne retient qu'un seuil APPRIS sur l'archive, 0 sinon.
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
# Règle des buts entiers (Patrick, 24/10/2026), marge d'un demi-but partout :
# - « plus de 1,5 » = au moins 2 buts -> accepté si le total attendu atteint 2 + 0,5 = 2,5 (marge 1,0 au-dessus de la ligne) ;
# - « moins de 2,5 » = en réalité « moins de 3 buts » -> accepté si le total attendu est au plus 3 - 0,5 = 2,5 (marge 0 sous la ligne).
# Même règle pour les buts par équipe (donc aussi « les deux marquent »). La marge n'est qu'un garde-fou : la fréquence de répétition
# (part des comparaisons au-dessus du seuil dans les deux branches) décide d'abord. Jamais recalculée.
DEMI_BUT = 0.5
MARGE_PLUS = 0.5 + DEMI_BUT        # ligne X,5 -> au moins X+1 buts -> attendu >= X+1+0,5 = ligne + 1,0
MARGE_MOINS = DEMI_BUT - 0.5       # ligne X,5 -> moins de X+1 buts -> attendu <= X+1-0,5 = ligne - 0,0
MARGE_BUT_ENTIER = MARGE_PLUS      # compatibilité


def coef_k(n: int) -> float | None:
    """None si l'échantillon est insuffisant (match exclu)."""
    if n < MIN_MATCHS:
        return None
    return K_PAR_ECHANTILLON.get(n, K_DEFAUT)


# --- Valeurs de départ : aucune marge imposée (24/10/2026) ------------------------------------------------------
DEFAUT = {
    "seuil_branche": 0.5,          # part minimale de scénarios validants dans CHAQUE branche (offensive et défensive)
    # Marge de niveau, en buts : « plus de L » exige attendu >= L + marge ; « moins de L » exige attendu <= L - marge.
    "marges": {
        "defaut": 0.0,
        "total_plus": {"1.5": MARGE_PLUS, "2.5": MARGE_PLUS, "3.5": MARGE_PLUS, "4.5": MARGE_PLUS},
        "total_moins": {"1.5": MARGE_MOINS, "2.5": MARGE_MOINS, "3.5": MARGE_MOINS, "4.5": MARGE_MOINS},
        "equipe_plus": {"0.5": MARGE_PLUS, "1.5": MARGE_PLUS, "2.5": MARGE_PLUS},
        "equipe_moins": {"0.5": MARGE_MOINS, "1.5": MARGE_MOINS, "2.5": MARGE_MOINS},
        "handicap_1_5": 0.0,
    },
    # Écart attendu d = buts attendus domicile - buts attendus extérieur.
    "seuils_resultat": {
        "dom_gagne": 0.0,          # victoire domicile : d >= seuil
        "ext_gagne": 0.0,          # victoire extérieur : d <= -seuil
        "dom_ne_perd_pas": 0.0,    # 1N et handicap +0,5 domicile : d >= seuil
        "ext_ne_perd_pas": 0.0,    # N2 et handicap +0,5 extérieur : d <= -seuil
        "nul": None,               # match nul : |d| <= seuil ; None = aucun seuil appris (le nul est alors rejeté au registre, avec la raison)
    },
    "multigoals": {
        "marge_borne": 0.0,        # le total attendu doit rester à au moins cette distance de chaque borne (aucune distance imposée depuis le 24/10/2026)
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
