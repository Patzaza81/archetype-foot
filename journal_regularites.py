"""Journal — mode « regularites » : formule simple, SANS cote et SANS ROI.

Indépendant de V2 et V3 (bibliothèque standard + journal_rentabilite uniquement).

Formule (décidée par le propriétaire) :
    chiffre = taux de réussite de l'équipe sur le marché  x  réalisme du marché  x  (1 - marge d'erreur relative)
- taux de réussite de l'équipe : gagnés / joués (ex. 8 sur 10 = 0,80) ;
- réalisme du marché : réussite RÉELLE de ce marché lors du match suivant, divisée par le taux affiché, mesurée sur toutes
  les régularités passées de ce marché (même règle d'entrée que le Journal), recalculée à chaque exécution ; moins de
  15 cas pour ce marché : réalisme moyen de tous les marchés ;
- marge d'erreur : taux moins sa borne basse à 95 % (Wilson), qui pénalise les petits échantillons même à 100 %.
On classe ensuite par ce chiffre. La probabilité utilisée pour les tickets est taux x réalisme (sans la marge).

Autres règles :
- entrée : au moins 5 matchs, réussite >= 70 %, marché non banal (journal_rentabilite, inchangé) ;
- constance : dès 6 matchs, la moyenne « réussite globale » et « réussite sur les 6 derniers matchs » doit atteindre 70 % ;
  avec 5 matchs, la réussite globale seule suffit ;
- la cote n'intervient dans aucun calcul ni critère du Journal (l'intervalle 1,26–3,01 du générateur reste une contrainte
  de tickets, pas un critère de sélection) ; aucun ROI, aucun gain espéré.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import journal_rentabilite as jr

MIN_MATCHS = 5
SEUIL_REUSSITE = 0.70
MATCHS_INDICE = 6          # l'indice « 6 derniers » s'applique dès 6 matchs
MIN_CAS_MARCHE = 15        # en dessous, réalisme moyen de tous les marchés
MIN_CAS_GLOBAL = 30        # en dessous, aucun réalisme fiable : aucun pari admissible

MOTIF_MATCHS = "MATCHS_INSUFFISANTS"
MOTIF_CONSTANCE = "CONSTANCE_INSUFFISANTE"
MOTIF_6_ABSENTS = "DONNEE_6_DERNIERS_ABSENTE"
MOTIF_REALISME = "REALISME_ABSENT"


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


def evalue(gagnes: int, joues: int, gagnes_6: Any, joues_6: Any) -> tuple[bool, list[str]]:
    """(admissible, motifs de rejet). La cote n'intervient pas. Toutes les conditions sont vérifiées pour que les motifs
    soient complets."""
    motifs: list[str] = []
    if joues < MIN_MATCHS:
        motifs.append(MOTIF_MATCHS)
    if joues >= MATCHS_INDICE:
        ind = indice_constance(gagnes, joues, gagnes_6, joues_6)
        if ind is None:
            motifs.append(MOTIF_6_ABSENTS)
        elif ind + 1e-9 < SEUIL_REUSSITE:
            motifs.append(MOTIF_CONSTANCE)
    elif joues >= MIN_MATCHS and joues > 0 and gagnes / joues + 1e-9 < SEUIL_REUSSITE:
        motifs.append(MOTIF_CONSTANCE)
    return (not motifs, motifs)


# --- formule simple : taux x réalisme x (1 - marge d'erreur) ------------------------------------------------------------

def borne_wilson(p: float, n: int, z: float = 1.959963984540054) -> float:
    """Borne basse à 95 % du taux p observé sur n cas (Wilson). Contrairement à la marge classique 1,96 x racine(p(1-p)/n),
    elle ne tombe pas à zéro quand p vaut 100 % : 5 sur 5 reste moins sûr que 18 sur 20."""
    if n <= 0:
        return 0.0
    den = 1.0 + z * z / n
    centre = p + z * z / (2.0 * n)
    ecart = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * n)) / n)
    return max(0.0, (centre - ecart) / den)


def marge_erreur(p: float, n: int) -> float:
    """Marge d'erreur à 95 % d'un taux p observé sur n cas : p moins sa borne basse. Plus n est petit, plus elle est grande."""
    if n <= 0:
        return p
    return max(0.0, p - borne_wilson(p, n))


def chiffre(taux: float, n: int, realisme: float) -> float:
    """Le chiffre de classement : taux x réalisme x (1 - marge d'erreur relative) = réalisme x borne basse du taux.
    Borné à [0, 1]."""
    if taux <= 0 or n <= 0:
        return 0.0
    facteur = 1.0 - marge_erreur(taux, n) / taux
    return max(0.0, min(1.0, taux * realisme * facteur))


def probabilite_ticket(taux: float, realisme: float) -> float:
    """Probabilité utilisée pour les tickets : taux x réalisme (sans la marge, qui sert au classement)."""
    return max(0.01, min(0.99, taux * realisme))


def candidats_passes(matchs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reconstruit, jour après jour et SANS fuite du futur, les paris que la règle d'entrée du Journal aurait retenus, avec
    leur résultat réel au match suivant. Aucune cote n'est utilisée : tous les matchs terminés servent. Un résultat
    remboursé est ignoré."""
    marches = jr.MARCHES_EQUIPE
    ordonnes = sorted(matchs, key=lambda m: (str(m.get("date")), str(m.get("match_id"))))
    par_jour: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for m in ordonnes:
        if m.get("buts"):
            par_jour[str(m["date"])].append(m)
    equipe: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    general: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    out: list[dict[str, Any]] = []

    def issue(lib: str, buts: Any) -> Any:
        an = jr.analyse_libelle(lib)
        return an[1](*buts) if an else None

    for jour in sorted(par_jour):
        for m in par_jour[jour]:
            for eq, cote_eq in ((m["domicile"], 0), (m["exterieur"], 1)):
                for nom, libs in marches.items():
                    g = general[nom]
                    if g[1] == 0 or g[0] / g[1] >= jr.SEUIL_FREQUENCE_EQUIPE:
                        continue
                    w, n = equipe[(eq, m["ligue"], nom)]
                    if n < jr.MIN_MATCHS_EQUIPE or w / n < jr.SEUIL_FREQUENCE_EQUIPE:
                        continue
                    r = issue(libs[cote_eq], m["buts"])
                    if r is None or r == 0:
                        continue
                    out.append({"date": jour, "equipe": eq, "marche": nom, "gagnes": w, "joues": n,
                                "frequence": w / n, "resultat": 1 if r == 1 else 0})
        for m in par_jour[jour]:
            for eq, cote_eq in ((m["domicile"], 0), (m["exterieur"], 1)):
                for nom, libs in marches.items():
                    r = issue(libs[cote_eq], m["buts"])
                    if r is None:
                        continue
                    equipe[(eq, m["ligue"], nom)][1] += 1
                    equipe[(eq, m["ligue"], nom)][0] += 1 if r == 1 else 0
                    general[nom][1] += 1
                    general[nom][0] += 1 if r == 1 else 0
    return out


def stats_realisme(candidats: list[dict[str, Any]]) -> dict[str, Any]:
    """Par marché : nombre de cas, somme des taux affichés, nombre de réussites réelles. + total tous marchés."""
    marches: dict[str, list[float]] = defaultdict(lambda: [0, 0.0, 0])
    total = [0, 0.0, 0]
    for c in candidats:
        for acc in (marches[c["marche"]], total):
            acc[0] += 1
            acc[1] += c["frequence"]
            acc[2] += c["resultat"]
    return {"marches": {k: tuple(v) for k, v in marches.items()}, "total": tuple(total), "erreur": None}


def realisme_pour(marche: str, stats: dict[str, Any] | None) -> tuple[float | None, str | None]:
    """(réalisme, origine). Réalisme = réussite réelle / taux affiché. Marché avec moins de 15 cas : réalisme de tous les
    marchés ; moins de 30 cas au total : None (aucun pari admissible)."""
    if not stats:
        return None, None
    n, somme, reussis = stats.get("marches", {}).get(marche, (0, 0.0, 0))
    if n >= MIN_CAS_MARCHE and somme > 0:
        return reussis / somme, "marche"
    n, somme, reussis = stats.get("total", (0, 0.0, 0))
    if n >= MIN_CAS_GLOBAL and somme > 0:
        return reussis / somme, "moyenne"
    return None, None


def charge_realisme(jusqu_a: str | None = None) -> dict[str, Any]:
    """Lit les résultats passés (date < jusqu_a si fournie) et calcule le réalisme de chaque marché. Une erreur de lecture est
    renvoyée dans « erreur » et jamais masquée : sans réalisme, aucun pari n'est admissible."""
    try:
        matchs = jr.charge_tous_resultats()
    except Exception as exc:  # noqa: BLE001 - l'erreur est exposée dans le diagnostic
        return {"marches": {}, "total": (0, 0.0, 0), "erreur": f"{type(exc).__name__}: {exc}"}
    if jusqu_a:
        matchs = [m for m in matchs if str(m.get("date") or "") < jusqu_a]
    return stats_realisme(candidats_passes(matchs))


# --- affichage -----------------------------------------------------------------------------------------------------------

def texte_affichage(equipe: str, gagnes: int, joues: int, gagnes_6: Any, joues_6: Any, taux_reel: float | None) -> str:
    """« 8 sur 10 » + réussite réelle de ce type de pari. Jamais de fréquence brute ni de borne de Wilson en pourcentage."""
    t = f"{equipe} : {gagnes} sur {joues} matchs sur ce marché"
    if joues >= MATCHS_INDICE and gagnes_6 is not None and joues_6:
        t += f" ({int(gagnes_6)} sur {int(joues_6)} sur les derniers)"
    if taux_reel is not None:
        t += f". Estimation de réussite pour ce match : {taux_reel:.0%}."
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
