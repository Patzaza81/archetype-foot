from __future__ import annotations

import datetime as dt
import json
import math
import random
import re
import unicodedata
from pathlib import Path
from typing import Any

INPUT = Path("data/selection_intelligence.json")
OUT = Path("data/tickets.json")

MAX_MATCHES = 12
# La cote totale d'un ticket est choisie par le parieur : toujours entre 2 et 20.
MIN_TARGET = 2.0
MAX_TARGET = 20.0
DEFAULT_TARGET = 10.0
# Fenêtres de proximité essayées dans l'ordre (±5 %, ±10 %, ±25 %), toujours bornées à [2 ; 20].
TOLERANCES = (0.05, 0.10, 0.25)
ODDS_MIN = 1.26
ODDS_MAX = 3.01
# DÉCISION DE PATRICK (09/10/2026) : V2.6.10 est exclu du générateur (trop instable pour l'instant ; le moteur et son
# archive continuent de tourner). Le générateur fait lui-même le tri dans chaque source (V3, Journal) et retient 15 paris
# au maximum par source, donc 30 au maximum. Pour réintégrer V2 : l'ajouter à SOURCES. Cela est fait pour 4 plages de dates cumulatives (jour présent, puis + 1 jour, + 2 jours, + 3 jours), les matchs commencés étant exclus. Ces 30 sont à égalité : les tickets sont tirés
# AU HASARD (graine = date du jour, enregistrée), sans règle de diversification de marchés, sans jamais réutiliser un
# match dans les tickets du jour. Aucun quota n'est rempli de force.
SOURCES = ("moteur_v3", "journal")
MAX_PAR_SOURCE = 15
POOL_MAX = MAX_PAR_SOURCE * len(SOURCES)
TENTATIVES_TIRAGE = 4000
# DÉCISION DE PATRICK (08/10/2026) : 4 plages cumulatives à partir du jour présent (heure du Cameroun, UTC+1) :
# jour présent ; jour présent + lendemain ; + surlendemain ; + J+3. Chaque plage a sa propre sélection (15 par source au
# maximum) et ses propres tickets. Les matchs déjà commencés sont exclus. Les dates sont affichées, jamais « J0 ».
NB_PLAGES = 4
FUSEAU_CAMEROUN = dt.timezone(dt.timedelta(hours=1))


def load(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.stat().st_size:
        return {}
    try:
        x = json.loads(path.read_text(encoding="utf-8"))
        return x if isinstance(x, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def n(x: Any) -> float | None:
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def implied(odds: Any) -> float | None:
    o = n(odds)
    return 1.0 / o if o and o > 1 else None


def proba(c: dict[str, Any]) -> float | None:
    """Probabilité normalisée du candidat, quelle que soit sa source."""
    p = n(c.get("probabilite"))
    if p is None:
        p = n(c.get("probabilite_estimee"))
    if p is None:
        q = implied(c.get("cote"))
        m = n(c.get("marge_succes"))
        if q is not None and m is not None:
            p = q + m
    return p if p is not None and 0.0 < p < 1.0 else None


def marge(c: dict[str, Any]) -> float | None:
    p, q = proba(c), implied(c.get("cote"))
    return p - q if p is not None and q is not None else None


def ev_leg(c: dict[str, Any]) -> float | None:
    p, o = proba(c), n(c.get("cote"))
    return p * o - 1.0 if p is not None and o else None


def rang_moteur(c: dict[str, Any]) -> int:
    return int(c.get("selection_rank") or {"P1": 3, "P2": 2, "P3": 1}.get(
        str(c.get("rang") or ""), 0
    ))


def candidate_rank(c: dict[str, Any]) -> tuple:
    """Classe les candidats avec les critères existants, après normalisation.

    Le générateur ne consulte jamais la source. V2.6.10, V3 et Journal arrivent
    sous le même contrat de sélection et sont comparés par la même clé lexicographique.
    """
    ev = ev_leg(c)
    lower = n(c.get("selection_evidence_lower_bound"))
    rate = n(c.get("selection_evidence_rate"))
    roi = n(c.get("selection_evidence_roi"))
    observations = int(c.get("selection_evidence_observations") or 0)
    sample_rank = int(c.get("selection_sample_rank") or 0)
    evidence = int(c.get("selection_evidence_rank") or 0)
    return (
        evidence,
        lower if lower is not None else -999.0,
        rate if rate is not None else -999.0,
        roi if roi is not None else -999.0,
        observations,
        sample_rank,
        int(c.get("calibrage_rang") or 0),
        n(c.get("calibrage_marge")) if c.get("calibrage_marge") is not None else -999.0,
        n(c.get("calibrage_lift")) if c.get("calibrage_lift") is not None else -999.0,
        rang_moteur(c),
        ev if ev is not None else -999.0,
        proba(c) or -999.0,
        -(n(c.get("cote")) or 99.0),
    )


def _nom_normalise(x: Any) -> str:
    texte = unicodedata.normalize("NFKD", str(x or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", texte).strip()


def match_key(c: dict[str, Any]) -> str:
    """Clé d'un match, la même quelle que soit la source : date + équipes (noms normalisés). Les identifiants et les heures
    ne servent pas, car le Journal n'en a pas (ou en a d'autres) et la même rencontre serait comptée deux fois.
    Équipes absentes : on retombe sur l'identifiant."""
    dom, ext = _nom_normalise(c.get("domicile")), _nom_normalise(c.get("exterieur"))
    if dom and ext:
        return "match:" + "|".join([str(c.get("date") or ""), dom, ext])
    mid = str(c.get("match_id") or "").strip()
    return "id:" + mid if mid else "match:" + str(c.get("date") or "") + "|" + dom + "|" + ext


def eligible(c: dict[str, Any], mode: str = "normal") -> bool:
    """Un choix est éligible si le moteur le voit au moins aussi probable que la cote ne le dit.
    Aucun historique minimal n'est exigé."""
    odds = n(c.get("cote"))
    if not odds or odds < ODDS_MIN or odds > ODDS_MAX:
        return False
    m, p = marge(c), proba(c)
    if m is None or p is None:
        return False
    if mode == "prudent":
        return m >= 0.03 and p >= 0.60
    return m >= 0.0


def dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[tuple[str, str, str], dict[str, Any]] = {}
    for c in rows:
        # Une même affiche/marché peut être proposée par V2, V3 et le Journal :
        # on conserve chaque source pour laisser le ticket exploiter leur avantage respectif.
        source = str(c.get("source") or c.get("moteur") or "inconnu").lower()
        k = (match_key(c), str(c.get("marche") or "").lower(), source)
        old = best.get(k)
        if old is None or candidate_rank(c) > candidate_rank(old):
            best[k] = dict(c)
    return sorted(best.values(), key=candidate_rank, reverse=True)


def distinct_match_count(rows: list[dict[str, Any]]) -> int:
    return len({match_key(x) for x in rows})


def source_count(rows: list[dict[str, Any]]) -> int:
    return len({x.get("source") for x in rows if x.get("source")})


def clamp_target(t: Any) -> float:
    v = n(t)
    if v is None:
        v = DEFAULT_TARGET
    return min(MAX_TARGET, max(MIN_TARGET, v))


def tolerance_tier(product: float, target: float) -> int | None:
    """Plus petite fenêtre de proximité contenant la cote totale, toujours dans [2 ; 20]."""
    for k, tol in enumerate(TOLERANCES):
        lo = max(MIN_TARGET, target * (1.0 - tol))
        hi = min(MAX_TARGET, target * (1.0 + tol))
        if lo - 1e-9 <= product <= hi + 1e-9:
            return k
    return None


def poisson_binomial(probs: list[float]) -> list[float]:
    """Loi du nombre de paris justes : dist[k] = P(exactement k justes), paris supposés indépendants."""
    dist = [1.0]
    for p in probs:
        nxt = [0.0] * (len(dist) + 1)
        for k, v in enumerate(dist):
            nxt[k] += v * (1.0 - p)
            nxt[k + 1] += v * p
        dist = nxt
    return dist


def plan_sizes(size: int, tickets: int) -> list[int]:
    """Tailles équilibrées : les premiers tickets reçoivent un pari en plus."""
    base, extra = divmod(size, tickets)
    return [base + 1 if i < extra else base for i in range(tickets)]


STRATEGIES = ("COTES_EQUILIBREES", "SECURITE_EQUILIBREE", "SECURITE_GROUPEE", "LIGUES_SEPAREES")


def _glouton(order: list[int], caps: list[int], poids: list[float], cout=None) -> list[list[int]]:
    """Affecte chaque pari (dans l'ordre donné) au ticket non plein de plus petit coût.
    Coût par défaut : somme des poids déjà dans le ticket. Égalités : plus petit indice de ticket."""
    t = len(caps)
    groups: list[list[int]] = [[] for _ in range(t)]
    sums = [0.0] * t
    for i in order:
        libres = [j for j in range(t) if len(groups[j]) < caps[j]]
        j = min(libres, key=(lambda j: (sums[j], j)) if cout is None else (lambda j: cout(groups, sums, j, i)))
        groups[j].append(i)
        sums[j] += poids[i]
    return [sorted(g) for g in groups]


def plan_partition(odds: list[float], tickets: int, probs: list[float] | None = None,
                   comps: list[str] | None = None, strategie: str = "COTES_EQUILIBREES") -> list[list[int]]:
    """Répartit les paris en `tickets` tickets disjoints selon une stratégie. Déterministe.

    - COTES_EQUILIBREES : cotes de tickets aussi proches que possible (maximise le retour garanti) ;
    - SECURITE_EQUILIBREE : probabilités de tickets aussi proches que possible ;
    - SECURITE_GROUPEE : les paris les plus sûrs ensemble, les plus risqués ensemble ;
    - LIGUES_SEPAREES : matchs d'une même compétition répartis dans des tickets différents."""
    n_ = len(odds)
    caps = plan_sizes(n_, tickets)
    lo = [math.log(o) for o in odds]
    if strategie == "COTES_EQUILIBREES" or probs is None:
        return _glouton(sorted(range(n_), key=lambda i: (-lo[i], i)), caps, lo)
    risque = [-math.log(p) for p in probs]
    if strategie == "SECURITE_EQUILIBREE":
        return _glouton(sorted(range(n_), key=lambda i: (-risque[i], i)), caps, risque)
    if strategie == "SECURITE_GROUPEE":
        ordre = sorted(range(n_), key=lambda i: (risque[i], i))
        groups, k = [], 0
        for c in caps:
            groups.append(sorted(ordre[k:k + c]))
            k += c
        return groups
    if strategie == "LIGUES_SEPAREES":
        cs = comps or [""] * n_

        def cout(groups, sums, j, i):
            return (sum(1 for x in groups[j] if cs[x] == cs[i]), sums[j], j)
        return _glouton(sorted(range(n_), key=lambda i: (-lo[i], i)), caps, lo, cout)
    raise ValueError(f"stratégie inconnue : {strategie}")


def plan_name(sizes: list[int], size: int) -> str:
    t = len(sizes)
    if t == 1:
        return "COMBINE"
    if t == size:
        return "SIMPLES"
    if min(sizes) == max(sizes):
        return f"TICKETS_{t}X{sizes[0]}"
    return f"TICKETS_{t}_DE_{min(sizes)}_A_{max(sizes)}"


def evalue_repartition(groups: list[list[int]], probs: list[float], odds: list[float]) -> dict[str, Any]:
    """Chiffres d'une répartition donnée : cotes et probabilités de tickets, retour garanti, erreurs garanties."""
    tickets = len(groups)
    t_odds, t_probs = [], []
    for g in groups:
        o = 1.0
        p = 1.0
        for i in g:
            o *= odds[i]
            p *= probs[i]
        t_odds.append(o)
        t_probs.append(p)
    inv = sum(1.0 / o for o in t_odds)
    ret = 1.0 / inv
    need = math.ceil(1.0 / ret - 1e-12)
    dist = poisson_binomial(t_probs)
    feasible = need <= tickets
    return {
        "composition": [
            {"paris": g, "cote": round(t_odds[j], 4), "probabilite": round(t_probs[j], 6),
             "mise": round((1.0 / t_odds[j]) / inv, 4)}
            for j, g in enumerate(groups)
        ],
        "retour_garanti": round(ret, 4),
        "gagnants_requis": need if feasible else None,
        "erreurs_garanties": tickets - need if feasible else None,
        "proba_profit": round(sum(dist[need:]), 4) if feasible else 0.0,
        "esperance_gain": round(ret * sum(t_probs) - 1.0, 4),
    }


def analyse_plan(probs: list[float], odds: list[float], tickets: int, comps: list[str] | None = None) -> dict[str, Any]:
    """Un plan = les n paris répartis en `tickets` tickets disjoints.

    Mise répartie au prorata de 1/cote du ticket : n'importe quel ticket gagnant rapporte alors
    R = 1 / Σ(1/cote_ticket) par unité misée, et W tickets gagnants rapportent R·W.
    Gagnants requis = plus petit W avec R·W ≥ 1. Une erreur fait perdre au plus un ticket,
    donc `erreurs_garanties` = tickets − gagnants requis est garanti quelle que soit leur place.

    Plusieurs répartitions (STRATEGIES) sont évaluées ; la meilleure est retenue : plus d'erreurs garanties,
    puis plus de chances d'être rentable, puis plus de gain espéré. À égalité, la première stratégie
    (cotes équilibrées) l'emporte. Les répartitions identiques ne sont comptées qu'une fois."""
    size = len(probs)
    vues: dict[tuple, str] = {}
    candidats: list[tuple[str, dict[str, Any]]] = []
    for strat in STRATEGIES:
        groups = plan_partition(odds, tickets, probs, comps, strat)
        cle = tuple(tuple(g) for g in groups)
        if cle in vues:
            continue
        vues[cle] = strat
        candidats.append((strat, evalue_repartition(groups, probs, odds)))

    def cle_tri(c: tuple[str, dict[str, Any]]) -> tuple:
        e = c[1]["erreurs_garanties"]
        return (e if e is not None else -1, c[1]["proba_profit"], c[1]["esperance_gain"])
    choisie = candidats[0]
    for c in candidats[1:]:
        if cle_tri(c) > cle_tri(choisie):
            choisie = c
    strat, ev = choisie
    sizes = [len(t["paris"]) for t in ev["composition"]]
    return {
        "nom": plan_name(sizes, size),
        "tickets": tickets,
        "tailles": sizes,
        "strategie": strat,
        "variantes": [
            {"strategie": s, "choisie": s == strat, "erreurs_garanties": e["erreurs_garanties"],
             "proba_profit": e["proba_profit"], "esperance_gain": e["esperance_gain"]}
            for s, e in candidats
        ],
        **ev,
    }


def analyse_ticket(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Marge d'erreur et rentabilité d'une sélection de n paris, pour chaque plan de tickets disjoints.

    Exemple : 12 paris en 4 tickets de 3. Si 3 paris sont faux dans 3 tickets différents, il reste
    1 ticket gagnant : rentable seulement si sa cote est assez haute (retour_garanti × gagnants ≥ 1).
    Paris supposés indépendants ; probabilités des moteurs non recalibrées."""
    probs = [proba(x) for x in rows]
    odds = [n(x.get("cote")) for x in rows]
    size = len(rows)
    if size < 2 or any(p is None for p in probs) or any(not o or o <= 1 for o in odds):
        return None
    dist = poisson_binomial(probs)
    counts = sorted({1, size} | set(range(2, size // 2 + 1)))
    comps = [str(x.get("competition") or "") for x in rows]
    plans = [analyse_plan(probs, odds, t, comps) for t in counts]
    best = max(plans, key=lambda p: p["esperance_gain"])
    positifs = [p for p in plans if p["esperance_gain"] > 0 and p["gagnants_requis"] is not None]
    regulier = max(positifs, key=lambda p: (p["proba_profit"], p["esperance_gain"])) if positifs else None
    marge = max(positifs, key=lambda p: (p["erreurs_garanties"], p["esperance_gain"])) if positifs else None
    return {
        "paris": size,
        "hypotheses": "Paris supposés indépendants ; probabilités des moteurs non recalibrées ; "
                      "le bookmaker doit accepter plusieurs tickets ; « profit » = mise au moins remboursée.",
        "probabilite_bonnes": [round(v, 6) for v in dist],
        "paris_justes_attendus": round(sum(probs), 4),
        "taux_estime_moyen": round(sum(probs) / size, 4),
        "plans": plans,
        "meilleur_plan": best["nom"],
        "plan_le_plus_regulier": regulier["nom"] if regulier else None,
        "plan_marge_max": marge["nom"] if marge else None,
        "rentable": best["esperance_gain"] > 0,
    }


def ticket_metrics(rows: list[dict[str, Any]], target: float | None = None) -> dict[str, Any]:
    odds = [n(x.get("cote")) for x in rows]
    odds = [x for x in odds if x and x > 1]
    product = math.prod(odds) if odds else None
    margins = [n(x.get("marge_succes")) for x in rows if n(x.get("marge_succes")) is not None]
    model_margins = [m for m in (marge(x) for x in rows) if m is not None]
    probs = [proba(x) for x in rows]
    joint = math.prod(probs) if rows and all(p is not None for p in probs) else None
    return {
        "matchs": len(rows),
        "cote_totale": round(product, 4) if product is not None else None,
        "ecart_objectif": round(abs(product - target), 4) if target and product else None,
        "marge_succes_min": round(min(margins), 6) if margins else None,
        "marge_succes_moyenne": round(sum(margins) / len(margins), 6) if margins else None,
        "marge_modele_moyenne": round(sum(model_margins) / len(model_margins), 6) if model_margins else None,
        "probabilite_independante_theorique": round(joint, 6) if joint is not None else None,
        "ev_theorique": round(joint * product - 1.0, 4) if joint is not None and product else None,
        "sources": sorted({x.get("source") for x in rows if x.get("source")}),
        "diversite_sources": source_count(rows),
        "niveau_min": min((int(x.get("rang_confiance") or 0) for x in rows), default=0),
    }


def leg(x: dict[str, Any]) -> dict[str, Any]:
    p, ev = proba(x), ev_leg(x)
    return {
        "match_id": x.get("match_id"),
        "cle_match": match_key(x),
        "date": x.get("date"),
        "heure": x.get("heure"),
        "competition": x.get("competition"),
        "domicile": x.get("domicile"),
        "exterieur": x.get("exterieur"),
        "marche": x.get("marche"),
        "cote": x.get("cote"),
        "probabilite": x.get("probabilite"),
        "probabilite_estimee": round(p, 6) if p is not None else None,
        "ev_estime": round(ev, 6) if ev is not None else None,
        "marge_modele": x.get("marge_modele"),
        "marge_succes": x.get("marge_succes"),
        "niveau_confiance": x.get("niveau_confiance"),
        "historique_observations": x.get("historique_observations"),
        "calibrage_externe": x.get("calibrage_externe"),
        "calibrage_rang": x.get("calibrage_rang"),
        "calibrage_marge": x.get("calibrage_marge"),
        "calibrage_lift": x.get("calibrage_lift"),
        "probabilite_source": x.get("probabilite_source"),
        "preuve_niveau": x.get("preuve_niveau"),
        "probabilite_brute_journal": x.get("probabilite_brute_journal"),
        "journal_frequency": x.get("journal_frequency"),
        "journal_wins": x.get("journal_wins"),
        "journal_observations": x.get("journal_observations"),
        "journal_lower_bound": x.get("journal_lower_bound"),
        "journal_roi": x.get("journal_roi"),
        "journal_team": x.get("journal_team"),
        "journal_opportunity": x.get("journal_opportunity"),
        "source": x.get("source"),
        "moteur": x.get("moteur"),
        "rang": x.get("rang"),
        "justification": x.get("justification"),
        "betpawa_url": x.get("betpawa_url"),
        "aussi_propose_par": x.get("aussi_propose_par") or [],
        "journal_calibrage": x.get("journal_calibrage"),
    }


def ticket(rows: list[dict[str, Any]], scenario: str, target: float | None = None) -> dict[str, Any]:
    return {
        "scenario": scenario,
        "statut": "OK" if rows else "AUCUN_TICKET_SOLIDE",
        "regle": "Un seul pari par match, jamais le même match dans deux tickets du jour, tirage au hasard (graine = date), aucun quota rempli artificiellement, maximum 12 matchs, cote totale entre 2 et 20.",
        "selection": [leg(x) for x in rows],
        "metrics": ticket_metrics(rows, target),
        "analyse": analyse_ticket(rows) if rows else None,
    }


def ordered_pool(rows: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    pool = [x for x in rows if eligible(x, mode)]
    if mode == "prudent":
        pool.sort(key=lambda c: (proba(c) or 0.0, ev_leg(c) or -999.0), reverse=True)
    else:
        pool.sort(key=candidate_rank, reverse=True)
    return pool


_TOTAL_JOURNAL = re.compile(r"^match à (plus|moins) de (\d+)[,.](\d+) buts$")


def marche_canonique(c: dict[str, Any]) -> str:
    """Nom de marché commun aux trois sources, pour reconnaître le MÊME pari proposé par deux sources.

    Les moteurs écrivent « over_under_total_3.5_under », le Journal « Match à moins de 3,5 buts ». Seuls les marchés
    dont l'équivalence est certaine sont traduits (totaux de buts, les deux équipes marquent, victoire et « ne perd pas »
    d'une équipe donnée). Les autres gardent leur nom : ils ne seront jamais pris à tort pour un doublon."""
    m = " ".join(str(c.get("marche") or "").split()).lower()
    t = _TOTAL_JOURNAL.match(m)
    if t:
        return f"over_under_total_{t.group(2)}.{t.group(3)}_{'over' if t.group(1) == 'plus' else 'under'}"
    if m == "les deux équipes marquent":
        return "btts_oui"
    if m == "au moins une équipe ne marque pas":
        return "btts_non"
    equipe = str(c.get("journal_team") or "").strip().lower()
    dom = str(c.get("domicile") or "").strip().lower()
    ext = str(c.get("exterieur") or "").strip().lower()
    if equipe and m == "victoire":
        return "1x2_domicile" if equipe == dom else "1x2_exterieur" if equipe == ext else m
    if equipe and m.startswith("ne perd pas"):
        return "double_chance_1X" if equipe == dom else "double_chance_X2" if equipe == ext else m
    return m


def pari_key(c: dict[str, Any]) -> tuple[str, str]:
    return (match_key(c), marche_canonique(c))


def candidats_source(data: dict[str, Any], source: str) -> list[dict[str, Any]]:
    """Tous les candidats d'une source. `candidats` (liste complète) si présent, sinon `top` (ancien format).
    V2.6.10 : uniquement le pronostic P1 (décision de Patrick du 08/10/2026)."""
    bloc = (data.get("sources", {}).get(source, {}) or {})
    rows = bloc.get("candidats")
    if not isinstance(rows, list):
        rows = bloc.get("top") or []
    rows = [dict(x) for x in rows if isinstance(x, dict)]
    if source == "moteur_v2_6_10":
        rows = [x for x in rows if str(x.get("rang") or "").upper() == "P1"]
    return rows


def selection_par_source(data: dict[str, Any]) -> tuple[dict[str, list[dict[str, Any]]], int]:
    """Tri fait par le générateur dans chaque source : paris jouables (cote 1,26–3,01, probabilité au moins égale à celle de
    la cote), classés par `candidate_rank`, 10 au maximum par source. Un même pari (même match, même marché) n'existe
    qu'une fois dans l'ensemble : il reste dans la source où il est le mieux classé, les autres le remplacent par leur
    pari suivant s'il existe (sinon la place reste vide, rien n'est forcé). Renvoie aussi le nombre de jouables."""
    listes = {s: [x for x in dedupe(candidats_source(data, s)) if eligible(x)] for s in SOURCES}
    meilleur: dict[tuple[str, str], tuple[tuple[int, int], str]] = {}
    for ordre, s in enumerate(SOURCES):
        for idx, x in enumerate(listes[s]):
            k = pari_key(x)
            if k not in meilleur or (idx, ordre) < meilleur[k][0]:
                meilleur[k] = ((idx, ordre), s)
    retenus: dict[str, list[dict[str, Any]]] = {}
    for s in SOURCES:
        gardes = [x for x in listes[s] if meilleur[pari_key(x)][1] == s][:MAX_PAR_SOURCE]
        for x in gardes:
            k = pari_key(x)
            x["aussi_propose_par"] = [t for t in SOURCES if t != s and any(pari_key(y) == k for y in listes[t])]
        retenus[s] = gardes
    return retenus, sum(len(v) for v in listes.values())


def _tirer_matchs_distincts(dispo: list[dict[str, Any]], size: int, rnd: random.Random) -> list[dict[str, Any]]:
    ordre = dispo[:]
    rnd.shuffle(ordre)
    chosen: list[dict[str, Any]] = []
    vus: set[str] = set()
    for x in ordre:
        mk = match_key(x)
        if mk in vus:
            continue
        chosen.append(x)
        vus.add(mk)
        if len(chosen) == size:
            break
    return chosen


def _disponibles(pool: list[dict[str, Any]], interdits: set[str]) -> list[dict[str, Any]]:
    return [x for x in pool if match_key(x) not in interdits and (n(x.get("cote")) or 0) > 1]


def tirage_ticket(pool: list[dict[str, Any]], size: int, graine: str, nom: str,
                  interdits: set[str] | None = None, tentatives: int = TENTATIVES_TIRAGE) -> list[dict[str, Any]]:
    """`size` paris sur `size` matchs différents, tirés AU HASARD dans `pool` (aucun classement, aucune règle de
    diversification). Les matchs de `interdits` (déjà pris par un autre ticket du jour) sont exclus. La cote totale doit
    être dans [2 ; 20] : sinon on retire. Même graine et même nom = même tirage. Rien de possible : liste vide."""
    interdits = interdits or set()
    dispo = _disponibles(pool, interdits)
    if size < 1 or len({match_key(x) for x in dispo}) < size:
        return []
    rnd = random.Random(f"{graine}|{nom}")
    for _ in range(tentatives):
        chosen = _tirer_matchs_distincts(dispo, size, rnd)
        if len(chosen) < size:
            return []
        produit = math.prod(float(x["cote"]) for x in chosen)
        if MIN_TARGET - 1e-9 <= produit <= MAX_TARGET + 1e-9:
            return chosen
    return []


def tirage_cible(pool: list[dict[str, Any]], target: float, graine: str, nom: str,
                 interdits: set[str] | None = None, tentatives: int = TENTATIVES_TIRAGE) -> list[dict[str, Any]]:
    """Ticket dont la cote totale est proche de `target` (toujours dans [2 ; 20]) : taille (2 à 12) et paris tirés au
    hasard ; on garde le premier tirage de la fenêtre de proximité la plus serrée trouvée. Rien de possible : liste vide."""
    target = clamp_target(target)
    interdits = interdits or set()
    dispo = _disponibles(pool, interdits)
    nb = len({match_key(x) for x in dispo})
    if nb < 2:
        return []
    rnd = random.Random(f"{graine}|{nom}")
    meilleur_tier: int | None = None
    retenu: list[dict[str, Any]] = []
    for _ in range(tentatives):
        size = rnd.randint(2, min(MAX_MATCHES, nb))
        chosen = _tirer_matchs_distincts(dispo, size, rnd)
        if len(chosen) < size:
            continue
        tier = tolerance_tier(math.prod(float(x["cote"]) for x in chosen), target)
        if tier is not None and (meilleur_tier is None or tier < meilleur_tier):
            meilleur_tier, retenu = tier, chosen
            if tier == 0:
                break
    return retenu


def build(data: dict[str, Any], graine: str | None = None) -> dict[str, Any]:
    # Le générateur trie lui-même chaque source (10 paris jouables au maximum chacune, 30 au total).
    retenus, nb_jouables = selection_par_source(data)
    pool = sorted([x for s in SOURCES for x in retenus[s]], key=candidate_rank, reverse=True)
    rows = pool
    graine = str(graine or data.get("graine_tirage") or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"))

    scenarios: list[dict[str, Any]] = []
    hors_intervalle: list[str] = []
    interdits: set[str] = set()                     # un match n'est utilisé qu'une fois pour tous les tickets du jour

    def add(chosen: list[dict[str, Any]], name: str, target: float | None = None) -> None:
        t = ticket(chosen, name, target)
        total = t["metrics"].get("cote_totale")
        if total is not None and not (MIN_TARGET - 1e-9 <= total <= MAX_TARGET + 1e-9):
            hors_intervalle.append(name)
            return
        scenarios.append(t)
        interdits.update(match_key(x) for x in chosen)

    prudents = [x for x in pool if eligible(x, "prudent")]
    for size, name in ((2, "PRUDENT_2"), (3, "PRUDENT_3"), (4, "EQUILIBRE_4"), (5, "EQUILIBRE_5")):
        chosen = tirage_ticket(prudents, size, graine, name, interdits)
        add(chosen if len(chosen) == size else [], name)

    chosen8 = tirage_ticket(pool, 8, graine, "EQUILIBRE_8", interdits)
    add(chosen8 if len(chosen8) == 8 else [], "EQUILIBRE_8")

    add(tirage_cible(pool, DEFAULT_TARGET, graine, "OBJECTIF_COTE_10", interdits), "OBJECTIF_COTE_10", DEFAULT_TARGET)

    return {
        "version": 3,
        "genere_le": dt.datetime.now(dt.timezone.utc).isoformat(),
        "graine_tirage": graine,
        "journal_calibrage": data.get("journal_calibrage"),
        "maximum_matchs": MAX_MATCHES,
        "maximum_par_source": MAX_PAR_SOURCE,
        "intervalle_cote_totale": [MIN_TARGET, MAX_TARGET],
        "cote_par_defaut": DEFAULT_TARGET,
        "tolerances": list(TOLERANCES),
        "principe": "Deux sources : V3 et Journal (V2.6.10 est exclu depuis le 09/10/2026). Le générateur trie chaque source (paris jouables, classement) et retient 15 paris au maximum par source, 30 au total, sans doublon de pari. Ces 30 sont à égalité : les tickets sont tirés au hasard (graine = date du jour), sans règle de diversification de marchés, sans jamais réutiliser un match dans les tickets du jour. Aucun quota n'est rempli de force. La cote totale est choisie par le parieur, entre 2 et 20.",
        "avertissement": "La cote totale d'un combiné est exacte comme produit des cotes observées ; la probabilité indépendante affichée n'est pas une probabilité jointe garantie.",
        "candidats_total": len(pool),
        "candidats_receptionnes": nb_jouables,
        "candidats_retenus": len(pool),
        "sources": {s: len(retenus[s]) for s in SOURCES},
        "pool": [leg(x) for x in pool],
        "opportunites": [
            leg(x) for x in rows
            if x.get("journal_opportunity")
            or int(x.get("historique_observations") or 0) >= 5
            or str(x.get("niveau") or "").startswith("V3_ECHANTILLON_")
            or int(x.get("calibrage_rang") or 0) > 0
        ][:20],
        "scenarios_hors_intervalle": hors_intervalle,
        "scenarios": scenarios,
    }


def maintenant_cameroun() -> dt.datetime:
    return dt.datetime.now(FUSEAU_CAMEROUN)


def deja_commence(c: dict[str, Any], maintenant: dt.datetime) -> bool:
    """Vrai si le match est passé ou a déjà commencé (date et heure du Cameroun). Heure absente ou illisible : on garde
    le match tant que sa date n'est pas passée (jamais d'exclusion sur une information qu'on n'a pas)."""
    jour = str(c.get("date") or "")
    aujourdhui = maintenant.date().isoformat()
    if not jour:
        return False
    if jour < aujourdhui:
        return True
    if jour > aujourdhui:
        return False
    m = re.match(r"^(\d{1,2}):(\d{2})", str(c.get("heure") or ""))
    if not m:
        return False
    return (int(m.group(1)), int(m.group(2))) <= (maintenant.hour, maintenant.minute)


def dates_plages(maintenant: dt.datetime) -> list[str]:
    jour = maintenant.date()
    return [(jour + dt.timedelta(days=i)).isoformat() for i in range(NB_PLAGES)]


def donnees_plage(data: dict[str, Any], dates: list[str], maintenant: dt.datetime) -> dict[str, Any]:
    """Copie des données ne gardant que les paris des dates de la plage, pas encore commencés."""
    def garde(c: dict[str, Any]) -> bool:
        return str(c.get("date") or "") in dates and not deja_commence(c, maintenant)

    sources = {}
    for nom, bloc in (data.get("sources") or {}).items():
        nouveau = dict(bloc)
        for cle in ("candidats", "top"):
            if cle in bloc:
                nouveau[cle] = [dict(c) for c in bloc.get(cle) or [] if garde(c)]
        sources[nom] = nouveau
    return {**data, "sources": sources}


CLES_PLAGE = ("candidats_total", "candidats_receptionnes", "candidats_retenus", "sources", "pool",
              "scenarios_hors_intervalle", "scenarios", "graine_tirage")


def build_plages(data: dict[str, Any], maintenant: dt.datetime | None = None) -> dict[str, Any]:
    """Une construction par plage. Le haut du fichier reprend la plus large (4 jours) : c'est elle que le suivi des
    tickets enregistre. `plages` contient les quatre, chacune avec ses dates (ISO) pour l'affichage."""
    maintenant = maintenant or maintenant_cameroun()
    jours = dates_plages(maintenant)
    plages: list[dict[str, Any]] = []
    dernier: dict[str, Any] = {}
    for n in range(1, NB_PLAGES + 1):
        dates = jours[:n]
        graine = f"{jours[0]}|{dates[0]}..{dates[-1]}"
        r = build(donnees_plage(data, dates, maintenant), graine)
        dernier = r
        plages.append({"id": f"{dates[0]}..{dates[-1]}", "debut": dates[0], "fin": dates[-1], "dates": dates,
                       **{k: r[k] for k in CLES_PLAGE}})
    return {**dernier, "jour_present": jours[0], "plage_par_defaut": plages[-1]["id"], "plages": plages}


def main() -> int:
    data = load(INPUT)
    if not data:
        result = {
            "version": 2,
            "genere_le": dt.datetime.now(dt.timezone.utc).isoformat(),
            "maximum_matchs": MAX_MATCHES,
            "maximum_par_source": MAX_PAR_SOURCE,
            "intervalle_cote_totale": [MIN_TARGET, MAX_TARGET],
            "cote_par_defaut": DEFAULT_TARGET,
            "candidats_total": 0,
            "pool": [],
            "opportunites": [],
            "scenarios": [],
            "statut_global": "DONNEES_INDISPONIBLES",
        }
    else:
        result = build_plages(data)
        result["statut_global"] = "OK" if result["candidats_total"] else "AUCUNE_OPPORTUNITE_SOLIDE"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"candidats": result["candidats_total"], "scenarios": len(result["scenarios"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
