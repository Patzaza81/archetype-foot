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
    """Probabilité estimée du choix : celle du moteur ; pour le Journal, celle du segment."""
    p = n(c.get("probabilite"))
    if p is None:
        p = n(c.get("probabilite_estimee"))
    if p is None and c.get("source") == "journal":
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
    r = {"P1": 3, "P2": 2, "P3": 1}.get(str(c.get("rang") or ""), 0)
    if r == 0 and c.get("source") == "journal":
        r = 2 if c.get("niveau") == "A_JOUER" else 1
    return r


def candidate_rank(c: dict[str, Any]) -> tuple:
    """Les moteurs font déjà le tri : rang P1/P2/P3, puis valeur estimée, puis probabilité.
    L'historique ne bloque rien ; il ne sert qu'à départager."""
    ev = ev_leg(c)
    return (
        rang_moteur(c),
        ev if ev is not None else -999.0,
        proba(c) or -999.0,
        int(c.get("historique_observations") or 0),
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
        # Une même affiche/marché peut être proposée par V2, V3 et le Journal :\n        # on conserve chaque source pour laisser le ticket exploiter leur avantage respectif.\n        source = str(c.get("source") or c.get("moteur") or "inconnu").lower()\n        k = (match_key(c), str(c.get("marche") or "").lower(), source)
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
    rows: list[dict[str, Any]] = []
    for source in ("moteur_v2_6_10", "moteur_v3", "journal"):
        rows.extend((data.get("sources", {}).get(source, {}) or {}).get("top", []) or [])
    rows = dedupe(rows)

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

    pool = ordered_pool(rows, "normal")[:POOL_MAX]
    return {
        "version": 2,
        "genere_le": dt.datetime.now(dt.timezone.utc).isoformat(),
        "maximum_matchs": MAX_MATCHES,
        "maximum_par_source": 10,
        "intervalle_cote_totale": [MIN_TARGET, MAX_TARGET],
        "cote_par_defaut": DEFAULT_TARGET,
        "tolerances": list(TOLERANCES),
        "principe": "Deux moteurs coexistants + Journal. Les moteurs font le tri : un choix est retenu si sa probabilité estimée dépasse la probabilité implicite de la cote, sans historique minimal. La cote totale est choisie par le parieur, entre 2 et 20, jamais hors de cet intervalle.",
        "avertissement": "La cote totale d'un combiné est exacte comme produit des cotes observées ; la probabilité indépendante affichée n'est pas une probabilité jointe garantie.",
        "candidats_total": len(rows),
        "sources": {source: len((data.get("sources", {}).get(source, {}) or {}).get("top", []) or []) for source in ("moteur_v2_6_10", "moteur_v3", "journal")},
        "pool": [leg(x) for x in pool],
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
