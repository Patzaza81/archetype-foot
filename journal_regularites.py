"""Journal — mode « regularites » : règles d'admissibilité et probabilité de ticket, SANS ROI.

Indépendant de V2 et V3 (bibliothèque standard + journal_rentabilite uniquement).

Règles (décidées par le propriétaire, voir docs/CLAUDE_RENTABILITE.md) :
- entrée : au moins 5 matchs, réussite >= 70 %, marché non banal (construit par journal_rentabilite, inchangé) ;
- cote entre 1,26 et 1,56 (plus de plafond 1,80) ;
- indice de constance : dès 6 matchs, la moyenne « réussite globale » et « réussite sur les 6 derniers matchs » doit
  atteindre 70 % ; avec 5 matchs, la réussite globale seule suffit ;
- probabilité utilisée pour les tickets : réussite OBSERVÉE pour la tranche de cote (pas de 0,10), calculée sur TOUS les
  résultats passés (pas seulement ceux du Journal) ; si la tranche a moins de 200 paris, valeur de l'intervalle entier ;
  recalculée à chaque exécution, jamais écrite en dur ;
- la borne de Wilson ne sert qu'au classement ; aucun ROI, aucun gain espéré.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import journal_rentabilite as jr

COTE_MIN = 1.26
COTE_MAX = 1.56
MIN_MATCHS = 5
SEUIL_REUSSITE = 0.70
MATCHS_INDICE = 6          # l'indice « 6 derniers » s'applique dès 6 matchs
MIN_PARIS_TRANCHE = 200    # en dessous, on prend la valeur de l'intervalle entier
PAS_TRANCHE = 0.10

MOTIF_COTE = "COTE_HORS_INTERVALLE"
MOTIF_MATCHS = "MATCHS_INSUFFISANTS"
MOTIF_CONSTANCE = "CONSTANCE_INSUFFISANTE"
MOTIF_6_ABSENTS = "DONNEE_6_DERNIERS_ABSENTE"
MOTIF_TAUX = "TAUX_OBSERVE_ABSENT"


def tranche(cote: float) -> float:
    """Tranche de cote par pas de 0,10 (1,26 -> 1,2 ; 1,34 -> 1,3 ; 1,50 -> 1,5)."""
    return round(math.floor(round(cote / PAS_TRANCHE, 6)) * PAS_TRANCHE, 1)


def dans_intervalle(cote: Any) -> bool:
    try:
        c = float(cote)
    except (TypeError, ValueError):
        return False
    return COTE_MIN <= c <= COTE_MAX


def indice_constance(gagnes: int, joues: int, gagnes_6: Any, joues_6: Any) -> float | None:
    """Réussite globale si moins de 6 matchs ; sinon moyenne à parts égales « globale + 6 derniers ».
    None si l'indice est exigé (>= 6 matchs) mais que la donnée des 6 derniers est absente : non vérifiable."""
    if joues <= 0:
        return None
    globale = gagnes / joues
    if joues < MATCHS_INDICE:
        return globale
    if gagnes_6 is None or joues_6 is None or int(joues_6) < MATCHS_INDICE:
        return None
    return (globale + int(gagnes_6) / int(joues_6)) / 2.0


def evalue(gagnes: int, joues: int, gagnes_6: Any, joues_6: Any, cote: Any) -> tuple[bool, list[str]]:
    """(admissible, motifs de rejet). Toutes les conditions sont vérifiées pour que les motifs soient complets."""
    motifs: list[str] = []
    if joues < MIN_MATCHS:
        motifs.append(MOTIF_MATCHS)
    if not dans_intervalle(cote):
        motifs.append(MOTIF_COTE)
    if joues >= MATCHS_INDICE:
        ind = indice_constance(gagnes, joues, gagnes_6, joues_6)
        if ind is None:
            motifs.append(MOTIF_6_ABSENTS)
        elif ind + 1e-9 < SEUIL_REUSSITE:
            motifs.append(MOTIF_CONSTANCE)
    elif joues >= MIN_MATCHS and joues > 0 and gagnes / joues + 1e-9 < SEUIL_REUSSITE:
        motifs.append(MOTIF_CONSTANCE)
    return (not motifs, motifs)


# --- réussite observée par tranche de cote ------------------------------------------------------------------------------

def taux_observes(matchs: list[dict[str, Any]]) -> dict[str, Any]:
    """Compte, sur TOUS les paris de TOUS les marchés dont la cote est dans l'intervalle, les réussites et les paris par
    tranche. Un résultat nul (remboursé) n'est ni une réussite ni un échec : il est ignoré."""
    par_tranche: dict[float, list[int]] = defaultdict(lambda: [0, 0])
    total = [0, 0]
    for m in matchs:
        cotes = m.get("cotes") or {}
        buts = m.get("buts")
        if not cotes or not buts:
            continue
        for lib, o in cotes.items():
            if not dans_intervalle(o):
                continue
            an = jr.analyse_libelle(lib)
            if not an:
                continue
            r = an[1](*buts)
            if r is None or r == 0:
                continue
            gagne = 1 if r == 1 else 0
            t = tranche(float(o))
            par_tranche[t][0] += gagne
            par_tranche[t][1] += 1
            total[0] += gagne
            total[1] += 1
    return {"tranches": {t: tuple(v) for t, v in sorted(par_tranche.items())}, "intervalle": tuple(total)}


def taux_pour(cote: float, stats: dict[str, Any] | None) -> tuple[float | None, str | None]:
    """(réussite observée, origine) pour une cote : tranche si >= 200 paris, sinon intervalle entier."""
    if not stats:
        return None, None
    w, n = stats.get("tranches", {}).get(tranche(cote), (0, 0))
    if n >= MIN_PARIS_TRANCHE:
        return w / n, "tranche"
    w, n = stats.get("intervalle", (0, 0))
    if n > 0:
        return w / n, "intervalle"
    return None, None


def charge_taux(jusqu_a: str | None = None) -> dict[str, Any]:
    """Lit les résultats passés (date < jusqu_a si fournie) et calcule les taux observés. Une erreur de lecture est
    renvoyée dans « erreur » et jamais masquée : sans taux, aucun pari n'est admissible."""
    try:
        matchs = jr.charge_tous_resultats()
    except Exception as exc:  # noqa: BLE001 - l'erreur est exposée dans le diagnostic
        return {"tranches": {}, "intervalle": (0, 0), "erreur": f"{type(exc).__name__}: {exc}"}
    if jusqu_a:
        matchs = [m for m in matchs if str(m.get("date") or "") < jusqu_a]
    stats = taux_observes(matchs)
    stats["erreur"] = None
    return stats


# --- affichage -----------------------------------------------------------------------------------------------------------

def texte_affichage(equipe: str, gagnes: int, joues: int, gagnes_6: Any, joues_6: Any, taux: float | None) -> str:
    """« 8 sur 10 » + réussite observée à cette cote. Jamais de fréquence brute ni de borne de Wilson en pourcentage."""
    t = f"{equipe} : {gagnes} sur {joues} matchs sur ce marché"
    if joues >= MATCHS_INDICE and gagnes_6 is not None and joues_6:
        t += f" ({int(gagnes_6)} sur {int(joues_6)} sur les derniers)"
    if taux is not None:
        t += f". À cette cote, ce type de pari réussit environ {taux:.0%} du temps."
    else:
        t += "."
    return t


# --- suivi quotidien -----------------------------------------------------------------------------------------------------

def enregistre_suivi(path: Path, jour: str, picks: list[dict[str, Any]]) -> dict[str, Any]:
    """Ajoute (ou remplace) la liste du jour dans le fichier de suivi. Les paris déjà résolus ne sont pas touchés."""
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError):
        data = {}
    jours = data.get("jours") if isinstance(data.get("jours"), dict) else {}
    existant = {(p.get("match"), p.get("marche")): p for p in (jours.get(jour) or []) if p.get("resultat") is not None}
    liste = []
    for c in picks:
        cle = (f"{c.get('domicile')} - {c.get('exterieur')}", c.get("marche"))
        liste.append(existant.get(cle) or {
            "match": cle[0], "marche": cle[1], "equipe": c.get("journal_team"), "cote": c.get("cote"),
            "gagnes": c.get("journal_wins"), "joues": c.get("journal_observations"),
            "taux_observe": c.get("probabilite_estimee"), "resultat": None,
        })
    jours[jour] = liste
    data = {"version": 1, "jours": jours}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return data


def resume_suivi(data: dict[str, Any]) -> dict[str, Any]:
    """Réussite réelle des paris résolus du suivi (1 = réussi, 0 = raté)."""
    res = [p["resultat"] for liste in (data.get("jours") or {}).values() for p in liste if p.get("resultat") in (0, 1)]
    return {"paris_resolus": len(res), "reussis": sum(res), "reussite": (sum(res) / len(res)) if res else None}


def _norm(x: Any) -> str:
    return " ".join(str(x or "").lower().split())


def resout_suivi(data: dict[str, Any], matchs: list[dict[str, Any]]) -> int:
    """Renseigne le résultat (1 = réussi, 0 = raté) des paris du suivi dont le match est terminé. Un match introuvable, un
    marché inconnu ou un résultat remboursé laissent le pari non résolu (jamais deviné). Renvoie le nombre de paris résolus."""
    index = {(str(m.get("date")), _norm(m.get("domicile")), _norm(m.get("exterieur"))): m for m in matchs}
    resolus = 0
    for jour, liste in (data.get("jours") or {}).items():
        for p in liste:
            if p.get("resultat") is not None:
                continue
            dom, _, ext = str(p.get("match") or "").partition(" - ")
            m = index.get((str(jour), _norm(dom), _norm(ext)))
            libs = jr.MARCHES_EQUIPE.get(p.get("marche"))
            if not m or not libs:
                continue
            lib = libs[0] if _norm(p.get("equipe")) == _norm(m.get("domicile")) else libs[1]
            an = jr.analyse_libelle(lib)
            if not an:
                continue
            r = an[1](*m["buts"])
            if r is None or r == 0:
                continue
            p["resultat"] = 1 if r == 1 else 0
            resolus += 1
    return resolus
