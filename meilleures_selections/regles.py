"""Règles pures de l'onglet « Meilleures sélections » (22/10/2026). Aucune lecture de fichier ici : tout est testable.

Un PARI = dict(moteur "V2"|"V3", date "AAAA-MM-JJ", marche (nom V3), cote, indice, sur, gagne 0|1).

Principe : le classement se recalibre seul. À chaque recalibrage, on regarde, pour chaque (moteur, famille de marché), les
ensembles « indice >= palier » (un palier par valeur d'indice observée) et on ne garde que ceux dont le résultat est
statistiquement meilleur que ce que les cotes exigent. Aucune constante tirée de l'intuition :
  - la base d'un pari = 1 / cote (ce que le bookmaker exige pour ne rien perdre) ;
  - le test = probabilité (loi binomiale exacte, base = moyenne des 1/cote) d'obtenir au moins autant de paris gagnés
    par hasard pur ; le résultat doit en plus dépasser la base dans CHAQUE moitié chronologique (précédent alpha_serie)
    et le rendement à mise égale doit être positif ;
  - les seuils de probabilité viennent du NOMBRE de tests POSSIBLES (m = somme sur les moteurs et les familles des paliers atteignables, fixé par la structure
    et non par la quantité de données, pour qu'un début d'historique ne relâche pas la règle) : « confirmé » = au plus une
    fausse admission attendue sur l'ensemble (p <= 1/m) ; « en observation » = p <= 1/racine(m).
Quand les données changent (m, n, résultats), les groupes entrent et sortent sans intervention.
"""
from __future__ import annotations

import math
import re
from datetime import date, timedelta
from typing import Any, Iterable, Mapping, Sequence

PERIODE_JOURS = 7  # recalibrage hebdomadaire (demande de Patrick)
MOTEURS = ("V2", "V3")


def nb_paliers(fam: str) -> int:
    """Paliers d'indice réellement possibles pour une famille (moteur_v3/performance.py) : marché d'une seule équipe = 2 scénarios
    (indice 0 à 2, donc 3 paliers) ; marché à deux équipes = 4 scénarios (indice 0 à 4, donc 5 paliers). Le nul n'a pas d'indice : aucun test."""
    if fam == "nul":
        return 0
    return 3 if fam in ("equipe_moins", "equipe_plus", "cage") else 5


def nb_tests_possibles() -> int:
    """Nombre de tests possibles, fixé par la structure (moteurs x familles x paliers atteignables), jamais par la quantité de données."""
    return len(MOTEURS) * sum(nb_paliers(f) for f in FAMILLES)

FAMILLES = {
    "total_moins": "Total de buts : moins de",
    "total_plus": "Total de buts : plus de",
    "equipe_moins": "Buts d'une équipe : moins de",
    "equipe_plus": "Buts d'une équipe : plus de",
    "handicap": "Handicap",
    "double_chance": "Double chance",
    "victoire": "Victoire d'une équipe",
    "nul": "Match nul",
    "btts_oui": "Les deux équipes marquent : oui",
    "btts_non": "Les deux équipes marquent : non",
    "cage": "Cage inviolée",
}


def famille(marche: str | None) -> str | None:
    """Famille d'un marché (nom V3). None si le marché n'est pas reconnu : il ne peut alors figurer dans aucun groupe."""
    s = str(marche or "")
    if re.fullmatch(r"under_\d_\d", s):
        return "total_moins"
    if re.fullmatch(r"over_\d_\d", s):
        return "total_plus"
    if re.fullmatch(r"(home|away)_under_\d_\d", s):
        return "equipe_moins"
    if re.fullmatch(r"(home|away)_over_\d_\d", s):
        return "equipe_plus"
    if s.startswith("handicap_"):
        return "handicap"
    if s.startswith("dc_"):
        return "double_chance"
    if s in ("1x2_1", "1x2_2"):
        return "victoire"
    if s == "1x2_x":
        return "nul"
    if s == "btts_yes":
        return "btts_oui"
    if s == "btts_no":
        return "btts_non"
    if s.startswith("clean_"):
        return "cage"
    return None


def niveau(p: Mapping[str, Any]) -> float | None:
    """Part des scénarios validés (indice / sur), entre 0 et 1. None si pas d'indice."""
    i, s = p.get("indice"), p.get("sur")
    if not isinstance(i, int) or not isinstance(s, int) or s <= 0:
        return None
    return i / s


def _jour(p: Mapping[str, Any]) -> str:
    return str(p.get("date") or "")[:10]


def _utilisable(p: Mapping[str, Any]) -> bool:
    return (famille(p.get("marche")) is not None and niveau(p) is not None
            and isinstance(p.get("cote"), (int, float)) and p["cote"] > 1 and p.get("gagne") in (0, 1, True, False))


def queue_binomiale(k: int, n: int, p: float) -> float:
    """P(X >= k) pour X ~ Binomiale(n, p), calcul exact (somme en logarithmes). p est borné à ]0, 1[."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    p = min(max(p, 1e-12), 1 - 1e-12)
    lp, lq = math.log(p), math.log(1 - p)
    termes = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq for i in range(k, n + 1)]
    m = max(termes)
    return min(1.0, math.exp(m) * sum(math.exp(t - m) for t in termes))


def statistiques(paris: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    n = len(paris)
    if n == 0:
        return {"n": 0, "gagnes": 0, "reussite": None, "base": None, "rendement": None, "erreur_type_rendement": None, "p": 1.0}
    g = sum(int(bool(p["gagne"])) for p in paris)
    base = sum(1.0 / p["cote"] for p in paris) / n
    gains = [(p["cote"] - 1.0) if p["gagne"] else -1.0 for p in paris]
    rend = sum(gains) / n
    var = sum((x - rend) ** 2 for x in gains) / (n - 1) if n > 1 else 0.0
    return {"n": n, "gagnes": g, "reussite": g / n, "base": base, "rendement": rend,
            "erreur_type_rendement": math.sqrt(var / n), "p": queue_binomiale(g, n, base)}


def _moitiés(paris: Sequence[Mapping[str, Any]]) -> tuple[list, list]:
    """Moitiés chronologiques : jours distincts triés, coupe au milieu (un jour n'est jamais coupé en deux)."""
    jours = sorted({_jour(p) for p in paris})
    if len(jours) < 2:
        return list(paris), []
    coupe = jours[len(jours) // 2]
    return [p for p in paris if _jour(p) < coupe], [p for p in paris if _jour(p) >= coupe]


def _tient_dans_le_temps(paris: Sequence[Mapping[str, Any]]) -> bool:
    premiere, seconde = _moitiés(paris)
    if not premiere or not seconde:
        return False
    for moitie in (premiere, seconde):
        s = statistiques(moitie)
        if s["reussite"] < s["base"]:
            return False
    return True


def candidats(paris: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Tous les ensembles testés : (moteur, famille, palier d'indice). Chaque ensemble = les paris de niveau >= palier."""
    utiles = [p for p in paris if _utilisable(p)]
    groupes: dict[tuple[str, str], list] = {}
    for p in utiles:
        groupes.setdefault((p["moteur"], famille(p["marche"])), []).append(p)
    out = []
    for (moteur, fam), lot in sorted(groupes.items()):
        for palier in sorted({niveau(p) for p in lot}):
            ens = [p for p in lot if niveau(p) >= palier]
            out.append({"moteur": moteur, "famille": fam, "palier": palier, "paris": ens})
    return out


def calibrer(paris: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Recalibrage complet à partir des seuls paris fournis (déjà résolus). Retourne les groupes admis et le détail des tests."""
    cands = candidats(paris)
    m = nb_tests_possibles()
    seuil_confirme = 1.0 / m if m else 0.0
    seuil_observation = 1.0 / math.sqrt(m) if m else 0.0
    tests = []
    for c in cands:
        s = statistiques(c["paris"])
        stable = _tient_dans_le_temps(c["paris"])
        ok_base = s["rendement"] is not None and s["rendement"] > 0 and s["reussite"] > s["base"] and stable
        statut = "confirme" if ok_base and s["p"] <= seuil_confirme else "observation" if ok_base and s["p"] <= seuil_observation else "rejete"
        tests.append({"moteur": c["moteur"], "famille": c["famille"], "palier": c["palier"], "statut": statut,
                      "stable_dans_le_temps": stable, **s})
    admis = []
    for (moteur, fam) in sorted({(t["moteur"], t["famille"]) for t in tests}):
        propres = [t for t in tests if t["moteur"] == moteur and t["famille"] == fam]
        for statut in ("confirme", "observation"):
            ok = [t for t in propres if t["statut"] == statut]
            if ok:
                admis.append(min(ok, key=lambda t: t["palier"]))   # le plus large des ensembles qui passent : aucun choix sur le gain
                break
    return {"m_tests": m, "nb_tests_realises": len(cands), "seuil_confirme": seuil_confirme, "seuil_observation": seuil_observation,
            "nb_paris": len([p for p in paris if _utilisable(p)]),
            "groupes": admis, "tests": tests}


def groupe_du_pari(pari: Mapping[str, Any], groupes: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """Groupe admis qui contient ce pari (même moteur, même famille, niveau >= palier). Le meilleur statut puis le plus petit p."""
    f, n = famille(pari.get("marche")), niveau(pari)
    if f is None or n is None:
        return None
    ok = [g for g in groupes if g["moteur"] == pari.get("moteur") and g["famille"] == f and n >= g["palier"] - 1e-12]
    if not ok:
        return None
    return sorted(ok, key=lambda g: (g["statut"] != "confirme", g["p"]))[0]


def classer(selections: Sequence[Mapping[str, Any]], groupes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Garde les sélections du jour appartenant à un groupe admis. Tri : confirmés d'abord, puis preuve la plus forte du groupe (p le plus bas), puis indice, probabilité et cote."""
    out = []
    for s in selections:
        g = groupe_du_pari(s, groupes)
        if g is not None:
            out.append({**s, "groupe": {k: g[k] for k in ("moteur", "famille", "palier", "statut", "n", "gagnes", "reussite", "base", "rendement", "p")}})
    out.sort(key=lambda x: (x["groupe"]["statut"] != "confirme", x["groupe"]["p"], -(niveau(x) or 0.0), -float(x.get("probabilite") or 0.0), -float(x.get("cote") or 0.0)))
    for i, x in enumerate(out, 1):
        x["rang"] = i
    return out


def recalibrage_du(historique: Sequence[Mapping[str, Any]], jour: str) -> bool:
    """Vrai si un recalibrage est dû : aucun jusqu'ici, ou le dernier date d'au moins PERIODE_JOURS jours."""
    if not historique:
        return True
    dernier = max(str(h["calibre_le"]) for h in historique)
    return date.fromisoformat(jour) - date.fromisoformat(dernier) >= timedelta(days=PERIODE_JOURS)


def photographie(paris: Sequence[Mapping[str, Any]], jour: str) -> dict[str, Any]:
    """Recalibre sur les paris STRICTEMENT antérieurs à `jour` et retourne l'instantané à archiver."""
    passes = [p for p in paris if _jour(p) < jour and _utilisable(p)]
    c = calibrer(passes)
    return {"calibre_le": jour, "nb_paris": len(passes), "m_tests": c["m_tests"], "seuil_confirme": c["seuil_confirme"],
            "seuil_observation": c["seuil_observation"], "groupes": c["groupes"]}


def bilan_historique(paris: Sequence[Mapping[str, Any]], groupes: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Résultat, par moteur, de l'ensemble des paris passés appartenant à au moins un groupe admis (chaque pari compté une fois).
    Mesure dans l'échantillon : ces paris ont servi à choisir les groupes, le chiffre est donc flatteur."""
    sortie: dict[str, list] = {}
    for p in paris:
        if _utilisable(p) and groupe_du_pari(p, groupes) is not None:
            sortie.setdefault(p["moteur"], []).append(p)
    return {m: statistiques(v) for m, v in sortie.items()}


def bilan_hors_echantillon(paris: Sequence[Mapping[str, Any]], historique: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Résultat des paris joués APRÈS le recalibrage qui les aurait retenus (le dernier instantané daté d'avant le pari).
    C'est la seule mesure non biaisée : aucun de ces paris n'a servi à choisir son groupe."""
    snaps = sorted(historique, key=lambda h: h["calibre_le"])
    sortie: dict[str, list] = {"confirme": [], "observation": []}
    for p in paris:
        if not _utilisable(p):
            continue
        actifs = [h for h in snaps if h["calibre_le"] <= _jour(p)]
        if not actifs:
            continue
        # un instantané daté du jour J ne couvre que les paris de J et après, calibrés sur les jours < J
        g = groupe_du_pari(p, actifs[-1]["groupes"])
        if g is not None:
            sortie[g["statut"]].append(p)
    return {k: statistiques(v) for k, v in sortie.items()}


def rejeu(paris: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Rejoue l'historique comme si le recalibrage hebdomadaire avait toujours tourné (marche avant, sans regarder l'avenir)."""
    jours = sorted({_jour(p) for p in paris if _utilisable(p)})
    if len(jours) <= PERIODE_JOURS:
        return {"instantanes": [], "bilan": bilan_hors_echantillon([], [])}
    debut = date.fromisoformat(jours[0]) + timedelta(days=PERIODE_JOURS)
    fin = date.fromisoformat(jours[-1])
    historique, j = [], debut
    while j <= fin:
        historique.append(photographie(paris, j.isoformat()))
        j += timedelta(days=PERIODE_JOURS)
    return {"instantanes": historique, "bilan": bilan_hors_echantillon(paris, historique)}
