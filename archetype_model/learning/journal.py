"""
archetype_model/learning/journal.py — Traçabilité de chaque cycle.

Pourquoi ce module existe : le cahier des charges v2 exige de pouvoir
répondre, des mois plus tard, "pourquoi ce seuil vaut-il actuellement
cette valeur ?" -- impossible sans une trace de CHAQUE cycle d'analyse,
même ceux où rien n'a été promu. Un cycle qui analyse et ne trouve rien à
changer doit être tracé comme tel, sinon on ne peut jamais distinguer
"le système n'a jamais tourné" de "le système a tourné et n'a rien trouvé
à changer".

Format : un fichier JSONL append-only (une ligne JSON par entrée), jamais
réécrit ni supprimé une fois une ligne ajoutée -- même principe que
historique_v0.jsonl, déjà en production pour le moteur V0.

Ce module n'a AUCUNE autorité de décision : il enregistre ce que
calibration.py (pas encore construit) lui fournit, sans jamais juger si
c'est correct. Toute validation revient à garde_fous.py, jamais à ce
module -- journal.py se contente de refuser un enregistrement
structurellement incomplet (champ obligatoire absent), jamais de juger le
fond d'une décision.

Deux journaux distincts, volontairement séparés :
- le journal de CYCLE (un résumé par passage, même quand rien n'est promu) ;
- le journal de PROMOTION (le détail de chaque proposition évaluée,
  promue, rejetée ou annulée par rollback).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CHAMPS_CYCLE_OBLIGATOIRES = (
    "date_cycle",
    "observations",
    "parametres_analyses",
    "propositions",
    "promotions",
    "rejets",
    "rollback",
    "constat_majeur",
)

CHAMPS_PROMOTION_OBLIGATOIRES = (
    "date_cycle",
    "parametre",
    "avant",
    "apres",
    "decision",
)

DECISIONS_VALIDES = frozenset({"PROMU", "REJETE", "ROLLBACK"})


def _ajoute_ligne(chemin: str, entree: dict[str, Any]) -> None:
    path = Path(chemin)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entree, ensure_ascii=False) + "\n")


def enregistrer_cycle(chemin: str, cycle: dict[str, Any]) -> None:
    """Ajoute une ligne au journal de cycle -- jamais une réécriture,
    jamais une suppression d'une ligne précédente."""
    for champ in CHAMPS_CYCLE_OBLIGATOIRES:
        if champ not in cycle:
            raise ValueError(f"champ obligatoire absent du cycle : {champ}")
    _ajoute_ligne(chemin, cycle)


def enregistrer_promotion(chemin: str, promotion: dict[str, Any]) -> None:
    """Ajoute une ligne au journal de promotion -- fichier séparé du
    journal de cycle, pour ne pas mélanger le résumé quotidien et le
    détail par paramètre."""
    for champ in CHAMPS_PROMOTION_OBLIGATOIRES:
        if champ not in promotion:
            raise ValueError(f"champ obligatoire absent de la promotion : {champ}")
    if promotion["decision"] not in DECISIONS_VALIDES:
        raise ValueError(
            f"decision invalide : {promotion['decision']!r} "
            f"(attendu un de {sorted(DECISIONS_VALIDES)})"
        )
    _ajoute_ligne(chemin, promotion)


def charger_journal(chemin: str) -> list[dict[str, Any]]:
    """Relit un journal (cycle ou promotion) complet, dans l'ordre
    d'écriture -- liste vide si le fichier n'existe pas encore, jamais une
    exception pour ce cas normal."""
    path = Path(chemin)
    if not path.exists():
        return []
    entrees = []
    with path.open("r", encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if ligne:
                entrees.append(json.loads(ligne))
    return entrees


def historique_parametre(chemin_promotions: str, parametre: str) -> list[dict[str, Any]]:
    """Filtre le journal de promotion pour un seul paramètre -- répond
    directement à 'pourquoi ce seuil vaut-il cette valeur aujourd'hui ?',
    dans l'ordre chronologique d'écriture."""
    return [p for p in charger_journal(chemin_promotions) if p.get("parametre") == parametre]
