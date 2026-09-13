"""
archetype_model/config_loader.py — Chargement des paramètres calibrables.

Pourquoi ce module existe : c'est le SEUL point de connexion entre le
moteur de décision (signals/convergence.py, poisson/robustness.py) et la
configuration externe produite par learning/calibration.py
(config/adaptive_parameters.json). Ne contient AUCUNE logique de décision
-- uniquement la lecture d'une valeur, avec repli sur la valeur d'origine
documentée ci-dessous si le fichier est absent, illisible ou incomplet.

Branché le 13/09/2026, avec feu vert explicite de Patrick -- première
modification touchant, même indirectement, le comportement de
signals/convergence.py et poisson/robustness.py depuis le début du
projet. Le principe reste celui du cahier des charges v2 §2.4 : seule la
VALEUR change de source, la logique de comparaison (if not COTE_MIN <=
cote <= COTE_MAX, etc.) reste identique, ligne pour ligne, dans les
fichiers protégés -- vérifié par diff avant livraison.

Repli en cas d'échec (fichier absent, JSON invalide, clé manquante,
valeur non numérique) : la valeur d'ORIGINE documentée dans ce fichier
même -- jamais None, jamais une exception qui interromprait le pipeline
nocturne. Un échec de lecture de la configuration ne doit jamais
empêcher le moteur de tourner. Le fichier absent est un cas NORMAL (par
exemple avant le tout premier déploiement de la configuration) -- aucun
avertissement. Le fichier présent mais avec une clé manquante ou une
valeur invalide est en revanche un signal d'un problème réel -- un
avertissement est écrit sur stderr, sans jamais bloquer.
"""

from __future__ import annotations

import json
import sys
from typing import Any

FICHIER_PARAMETRES_DEFAUT = "config/adaptive_parameters.json"

# Valeurs d'origine, IDENTIQUES à celles qui étaient codées en dur dans
# convergence.py et robustness.py avant ce branchement (cahier des
# charges v2 + Addendum 2). Le repli utilise TOUJOURS ces valeurs, jamais
# une estimation ni une valeur recalculée.
VALEURS_ORIGINE: dict[str, float] = {
    "COTE_MIN": 1.26,
    "COTE_MAX": 1.74,
    "ROBUSTNESS_STD_THRESHOLD": 0.08,
    "EDV_MIN_P_GE_75": 0.05,
    "EDV_MIN_P_71_75": 0.05,
    "EDV_MIN_P_67_71": 0.07,
    "EDV_MIN_P_63_67": 0.10,
    "EDV_MIN_P_60_63": 0.12,
}


def _charge_fichier(chemin: str) -> dict[str, Any] | None:
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None  # cas normal, aucun avertissement
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[config_loader] {chemin} illisible ({exc}) -- repli sur les valeurs d'origine", file=sys.stderr)
        return None


def valeur_parametre(nom: str, chemin: str = FICHIER_PARAMETRES_DEFAUT) -> float:
    """Retourne la valeur active de `nom` depuis le fichier de
    configuration, ou sa valeur d'origine documentée si le fichier est
    absent, illisible, si `nom` n'y figure pas, ou si sa valeur n'est pas
    numérique. Ne lève jamais d'exception pour ces cas -- uniquement si
    `nom` n'est pas un paramètre calibrable connu du tout (erreur de
    programmation à corriger, pas un incident d'exploitation)."""
    if nom not in VALEURS_ORIGINE:
        raise ValueError(f"{nom!r} n'est pas un paramètre calibrable connu de config_loader")

    contenu = _charge_fichier(chemin)
    if contenu is None:
        return VALEURS_ORIGINE[nom]

    bloc = (contenu.get("parametres") or {}).get(nom)
    if not isinstance(bloc, dict) or "valeur" not in bloc:
        print(f"[config_loader] {nom!r} absent ou mal formé dans {chemin} -- repli sur la valeur d'origine", file=sys.stderr)
        return VALEURS_ORIGINE[nom]

    valeur = bloc["valeur"]
    if not isinstance(valeur, (int, float)) or isinstance(valeur, bool):
        print(f"[config_loader] valeur non numérique pour {nom!r} dans {chemin} -- repli sur la valeur d'origine", file=sys.stderr)
        return VALEURS_ORIGINE[nom]

    return float(valeur)
