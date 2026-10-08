from __future__ import annotations

import datetime as dt
import json
import math
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
BEAM_WIDTH = 600
POOL_MAX = 30


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


def match_key(c: dict[str, Any]) -> str:
    mid = str(c.get("match_id") or "").strip()
    if mid:
        return "id:" + mid
    return "match:" + "|".join([
        str(c.get("date") or ""),
        str(c.get("heure") or ""),
        str(c.get("domicile") or "").lower(),
        str(c.get("exterieur") or "").lower(),
    ])


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
    }


def ticket(rows: list[dict[str, Any]], scenario: str, target: float | None = None) -> dict[str, Any]:
    return {
        "scenario": scenario,
        "statut": "OK" if rows else "AUCUN_TICKET_SOLIDE",
        "regle": "Un seul pari par match, aucun quota rempli artificiellement, maximum 12 matchs, cote totale entre 2 et 20.",
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


def greedy(rows: list[dict[str, Any]], size: int, mode: str) -> list[dict[str, Any]]:
    pool = ordered_pool(rows, mode)
    chosen: list[dict[str, Any]] = []
    seen_matches: set[str] = set()
    seen_groups: set[str] = set()
    for c in pool:
        mk = match_key(c)
        if mk in seen_matches:
            continue
        group = str(c.get("exposure_group") or c.get("market_family") or "")
        # La diversité de marchés est privilégiée sans devenir une interdiction
        # : si le groupe manque, on accepte un doublon plutôt que d'inventer un pari.
        if group and group in seen_groups and len(chosen) < size - 1:
            continue
        chosen.append(c)
        seen_matches.add(mk)
        if group:
            seen_groups.add(group)
        if len(chosen) == size:
            break
    # Deuxième passage : compléter seulement avec des candidats déjà jugés éligibles.
    if len(chosen) < size:
        for c in pool:
            if len(chosen) == size:
                break
            if match_key(c) not in seen_matches:
                chosen.append(c)
                seen_matches.add(match_key(c))
    return chosen


def beam_target(rows: list[dict[str, Any]], size: int, target: float) -> list[dict[str, Any]]:
    """Meilleure combinaison de `size` matchs dont la cote totale est proche de `target`
    (toujours dans [2 ; 20]) : à proximité égale, la plus forte probabilité conjointe,
    donc la plus forte valeur espérée à cote totale donnée."""
    target = clamp_target(target)
    pool = ordered_pool(rows, "normal")[:POOL_MAX]
    if size < 1 or len(pool) < size:
        return []
    log_target = math.log(target)
    log_cap = math.log(min(MAX_TARGET, target * (1.0 + TOLERANCES[-1])))

    states: list[tuple[tuple[int, ...], float]] = [((), 0.0)]
    for depth in range(1, size + 1):
        goal = log_target * depth / size
        nxt: list[tuple[tuple[int, ...], float]] = []
        for indices, log_prod in states:
            start = indices[-1] + 1 if indices else 0
            used = {match_key(pool[i]) for i in indices}
            for i in range(start, len(pool)):
                if match_key(pool[i]) in used:
                    continue
                odds = n(pool[i].get("cote"))
                if not odds or odds <= 1:
                    continue
                nlp = log_prod + math.log(odds)
                if nlp > log_cap + 1e-12:
                    continue
                nxt.append((indices + (i,), nlp))
        nxt.sort(key=lambda s: abs(s[1] - goal))
        states = nxt[:BEAM_WIDTH]
        if not states:
            return []

    best: list[dict[str, Any]] = []
    best_key = None
    for indices, log_prod in states:
        tier = tolerance_tier(math.exp(log_prod), target)
        if tier is None:
            continue
        chosen = [pool[i] for i in indices]
        joint = sum(math.log(proba(x)) for x in chosen)
        key = (-tier, joint, -abs(log_prod - log_target))
        if best_key is None or key > best_key:
            best_key, best = key, chosen
    return best


def best_target_ticket(rows: list[dict[str, Any]], target: float) -> list[dict[str, Any]]:
    """Le nombre de matchs reste adaptatif (2 à 12) ; la cote totale, elle, est imposée."""
    target = clamp_target(target)
    best: list[dict[str, Any]] = []
    best_key = None
    for size in range(2, MAX_MATCHES + 1):
        cand = beam_target(rows, size, target)
        if not cand:
            continue
        product = math.prod(float(x["cote"]) for x in cand)
        tier = tolerance_tier(product, target)
        if tier is None:
            continue
        joint = sum(math.log(proba(x)) for x in cand)
        key = (-tier, joint, -abs(math.log(product / target)))
        if best_key is None or key > best_key:
            best_key, best = key, cand
    return best


def build(data: dict[str, Any]) -> dict[str, Any]:
    # Les trois sources fournissent au maximum 10 candidats chacune.
    # Ils sont ensuite fusionnés sans traitement différencié dans le générateur.
    rows: list[dict[str, Any]] = []
    source_names = ("moteur_v2_6_10", "moteur_v3", "journal")
    for source in source_names:
        # Garde-fou : même si une source publie accidentellement plus de 10 lignes,
        # le contrat d'entrée du générateur reste strictement limité à 10 par source.
        rows.extend(((data.get("sources", {}).get(source, {}) or {}).get("top", []) or [])[:10])
    rows = dedupe(rows)

    # Sélection finale : les critères de classement existants restent inchangés.
    # Les tickets ne peuvent utiliser que ces 15 meilleurs candidats.
    pool_30 = ordered_pool(rows, "normal")[:POOL_MAX]
    retenus = pool_30[:15]
    rows = retenus

    scenarios: list[dict[str, Any]] = []
    hors_intervalle: list[str] = []

    def add(chosen: list[dict[str, Any]], name: str, target: float | None = None) -> None:
        t = ticket(chosen, name, target)
        total = t["metrics"].get("cote_totale")
        if total is not None and not (MIN_TARGET - 1e-9 <= total <= MAX_TARGET + 1e-9):
            hors_intervalle.append(name)
            return
        scenarios.append(t)

    for size, name in ((2, "PRUDENT_2"), (3, "PRUDENT_3"), (4, "EQUILIBRE_4"), (5, "EQUILIBRE_5")):
        chosen = greedy(rows, size, "prudent")
        add(chosen if len(chosen) == size else [], name)

    chosen8 = greedy(rows, 8, "normal")
    add(chosen8 if len(chosen8) == 8 else [], "EQUILIBRE_8")

    add(best_target_ticket(rows, DEFAULT_TARGET), "OBJECTIF_COTE_10", DEFAULT_TARGET)

    pool = retenus
    return {
        "version": 2,
        "genere_le": dt.datetime.now(dt.timezone.utc).isoformat(),
        "maximum_matchs": MAX_MATCHES,
        "maximum_par_source": 10,
        "intervalle_cote_totale": [MIN_TARGET, MAX_TARGET],
        "cote_par_defaut": DEFAULT_TARGET,
        "tolerances": list(TOLERANCES),
        "principe": "Deux moteurs coexistants + Journal. Les preuves observées (forme équipe du Journal et historique moteur) sont classées avant les probabilités moteur non calibrées. Pour un ticket, le Journal et un historique suffisant utilisent une borne Wilson prudente ; les probabilités moteur non calibrées restent signalées comme telles. La cote totale est choisie par le parieur, entre 2 et 20.",
        "avertissement": "La cote totale d'un combiné est exacte comme produit des cotes observées ; la probabilité indépendante affichée n'est pas une probabilité jointe garantie.",
        "candidats_total": len(pool_30),
        "candidats_receptionnes": len(rows) + (len(pool_30) - len(retenus)),
        "candidats_retenus": len(retenus),
        "minimum_retenus": 15,
        "sources": {source: min(10, len((data.get("sources", {}).get(source, {}) or {}).get("top", []) or [])) for source in source_names},
        "pool_30_receptionne": [leg(x) for x in pool_30],
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


def main() -> int:
    data = load(INPUT)
    if not data:
        result = {
            "version": 2,
            "genere_le": dt.datetime.now(dt.timezone.utc).isoformat(),
            "maximum_matchs": MAX_MATCHES,
            "maximum_par_source": 10,
            "intervalle_cote_totale": [MIN_TARGET, MAX_TARGET],
            "cote_par_defaut": DEFAULT_TARGET,
            "candidats_total": 0,
            "pool": [],
            "opportunites": [],
            "scenarios": [],
            "statut_global": "DONNEES_INDISPONIBLES",
        }
    else:
        result = build(data)
        result["statut_global"] = "OK" if result["candidats_total"] else "AUCUNE_OPPORTUNITE_SOLIDE"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"candidats": result["candidats_total"], "scenarios": len(result["scenarios"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
