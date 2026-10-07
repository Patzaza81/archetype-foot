from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

INPUT = Path("data/selection_intelligence.json")
OUT = Path("data/tickets.json")
MAX_MATCHES = 12


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


def candidate_rank(c: dict[str, Any]) -> tuple:
    return (
        int(c.get("rang_confiance") or 0),
        n(c.get("marge_succes")) if c.get("marge_succes") is not None else -999,
        n(c.get("marge_modele")) if c.get("marge_modele") is not None else -999,
        n(c.get("probabilite")) if c.get("probabilite") is not None else -999,
        n(c.get("edv")) if c.get("edv") is not None else -999,
        int(c.get("historique_observations") or 0),
        -(n(c.get("cote")) or 99),
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
    odds = n(c.get("cote"))
    if not odds or odds < 1.26 or odds > 3.01:
        return False
    confidence = int(c.get("rang_confiance") or 0)
    margin_success = n(c.get("marge_succes"))
    margin_model = n(c.get("marge_modele"))
    if mode == "prudent":
        return confidence >= 4 or (
            confidence >= 2 and margin_success is not None and margin_success > 0 and odds <= 1.75
        )
    if mode == "target":
        return confidence >= 2 or (
            margin_model is not None and margin_model >= 0.03 and
            n(c.get("probabilite")) is not None and n(c.get("probabilite")) >= 0.60
        )
    return confidence >= 2 or (
        margin_model is not None and margin_model >= 0.03 and
        n(c.get("probabilite")) is not None and n(c.get("probabilite")) >= 0.60
    )


def dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for c in rows:
        k = (match_key(c), str(c.get("marche") or "").lower())
        old = best.get(k)
        if old is None or candidate_rank(c) > candidate_rank(old):
            best[k] = dict(c)
    return sorted(best.values(), key=candidate_rank, reverse=True)


def distinct_match_count(rows: list[dict[str, Any]]) -> int:
    return len({match_key(x) for x in rows})


def source_count(rows: list[dict[str, Any]]) -> int:
    return len({x.get("source") for x in rows if x.get("source")})


def ticket_metrics(rows: list[dict[str, Any]], target: float | None = None) -> dict[str, Any]:
    odds = [n(x.get("cote")) for x in rows]
    odds = [x for x in odds if x and x > 1]
    product = math.prod(odds) if odds else None
    margins = [n(x.get("marge_succes")) for x in rows if n(x.get("marge_succes")) is not None]
    model_margins = [n(x.get("marge_modele")) for x in rows if n(x.get("marge_modele")) is not None]
    probs = [n(x.get("probabilite")) for x in rows if n(x.get("probabilite")) is not None]
    return {
        "matchs": len(rows),
        "cote_totale": round(product, 4) if product is not None else None,
        "ecart_objectif": round(abs(product - target), 4) if target and product else None,
        "marge_succes_min": round(min(margins), 6) if margins else None,
        "marge_succes_moyenne": round(sum(margins) / len(margins), 6) if margins else None,
        "marge_modele_moyenne": round(sum(model_margins) / len(model_margins), 6) if model_margins else None,
        "probabilite_independante_theorique": round(math.prod(probs), 6) if len(probs) == len(rows) else None,
        "sources": sorted({x.get("source") for x in rows if x.get("source")}),
        "diversite_sources": source_count(rows),
        "niveau_min": min((int(x.get("rang_confiance") or 0) for x in rows), default=0),
    }


def ticket(rows: list[dict[str, Any]], scenario: str, target: float | None = None) -> dict[str, Any]:
    metrics = ticket_metrics(rows, target)
    return {
        "scenario": scenario,
        "statut": "OK" if rows else "AUCUN_TICKET_SOLIDE",
        "regle": "Un seul pari par match, aucun quota rempli artificiellement, maximum 12 matchs.",
        "selection": [
            {
                "match_id": x.get("match_id"),
                "date": x.get("date"),
                "heure": x.get("heure"),
                "competition": x.get("competition"),
                "domicile": x.get("domicile"),
                "exterieur": x.get("exterieur"),
                "marche": x.get("marche"),
                "cote": x.get("cote"),
                "probabilite": x.get("probabilite"),
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
            for x in rows
        ],
        "metrics": metrics,
    }


def greedy(rows: list[dict[str, Any]], size: int, mode: str) -> list[dict[str, Any]]:
    pool = [x for x in rows if eligible(x, mode)]
    pool.sort(key=candidate_rank, reverse=True)
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
    # Deuxième passage : compléter seulement avec des candidats déjà jugés solides.
    if len(chosen) < size:
        for c in pool:
            if len(chosen) == size:
                break
            if match_key(c) not in seen_matches:
                chosen.append(c)
                seen_matches.add(match_key(c))
    return chosen


def beam_target(rows: list[dict[str, Any]], size: int, target: float) -> list[dict[str, Any]]:
    pool = [x for x in rows if eligible(x, "target")]
    pool.sort(key=candidate_rank, reverse=True)
    pool = pool[:30]
    if len(pool) < size:
        return []

    states: list[tuple[list[int], float]] = [([], 1.0)]
    beam_width = 350
    for depth in range(size):
        nxt: list[tuple[list[int], float]] = []
        for indices, product in states:
            start = indices[-1] + 1 if indices else 0
            used = {match_key(pool[i]) for i in indices}
            for i in range(start, len(pool)):
                if match_key(pool[i]) in used:
                    continue
                odds = n(pool[i].get("cote"))
                if not odds:
                    continue
                new_product = product * odds
                if new_product > target * 1.45:
                    continue
                new_indices = indices + [i]
                # Plus proche de la cible, puis meilleure preuve.
                distance = abs(math.log(max(new_product, 1e-9) / target))
                quality = candidate_rank(pool[i])
                score = distance - 0.000001 * sum(float(v or 0) for v in quality[1:4])
                nxt.append((new_indices, score))
        nxt.sort(key=lambda x: x[1])
        states = nxt[:beam_width]
        if not states:
            return []

    best_rows: list[dict[str, Any]] = []
    best_key = None
    for indices, _ in states:
        chosen = [pool[i] for i in indices]
        product = math.prod(float(x["cote"]) for x in chosen)
        metrics = ticket_metrics(chosen, target)
        # Qualité minimale avant proximité : aucune combinaison faible ne bat une combinaison solide
        # uniquement parce qu'elle atteint mieux la cote cible.
        key = (
            metrics["niveau_min"],
            metrics["marge_succes_min"] if metrics["marge_succes_min"] is not None else -999,
            -abs(math.log(product / target)),
            metrics["diversite_sources"],
            metrics["marge_modele_moyenne"] if metrics["marge_modele_moyenne"] is not None else -999,
        )
        if best_key is None or key > best_key:
            best_key = key
            best_rows = chosen
    return best_rows


def build(data: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for source in ("moteur_v2_6_10", "moteur_v3", "journal"):
        rows.extend((data.get("sources", {}).get(source, {}) or {}).get("top", []) or [])
    rows = dedupe(rows)

    scenarios: list[dict[str, Any]] = []
    for size, name in ((2, "PRUDENT_2"), (3, "PRUDENT_3"), (4, "EQUILIBRE_4"), (5, "EQUILIBRE_5")):
        chosen = greedy(rows, size, "prudent")
        scenarios.append(ticket(chosen if len(chosen) == size else [], name))

    chosen8 = greedy(rows, 8, "normal")
    scenarios.append(ticket(chosen8 if len(chosen8) == 8 else [], "EQUILIBRE_8"))

    # La cible de cote est une contrainte ; le nombre de matchs reste adaptatif, de 2 à 12.
    best_target = chosen10
    best_dist = float("inf")
    for size in range(2, MAX_MATCHES + 1):
        cand = beam_target(rows, size, 10.0)
        if not cand:
            continue
        product = math.prod(float(x["cote"]) for x in cand)
        dist = abs(math.log(product / 10.0))
        quality = ticket_metrics(cand, 10.0)
        if (
            quality["niveau_min"],
            quality["marge_succes_min"] if quality["marge_succes_min"] is not None else -999,
            -dist,
        ) > (
            ticket_metrics(best_target, 10.0)["niveau_min"] if best_target else 0,
            ticket_metrics(best_target, 10.0)["marge_succes_min"] if best_target and ticket_metrics(best_target, 10.0)["marge_succes_min"] is not None else -999,
            -best_dist,
        ):
            best_target, best_dist = cand, dist
    scenarios.append(ticket(best_target, "OBJECTIF_COTE_10", 10.0))

    chosen12 = greedy(rows, 12, "normal")
    scenarios.append(ticket(chosen12 if len(chosen12) == 12 else [], "OPPORTUNITES_12"))

    return {
        "version": 1,
        "genere_le": dt.datetime.now(dt.timezone.utc).isoformat(),
        "maximum_matchs": MAX_MATCHES,
        "maximum_par_source": 10,
        "principe": "Deux moteurs coexistants + Journal. Aucun moteur n'est remplacé. Un ticket n'est publié que si ses jambes passent les critères de solidité disponibles.",
        "avertissement": "La cote totale d'un combiné est exacte comme produit des cotes observées ; la probabilité indépendante affichée n'est pas une probabilité jointe garantie.",
        "candidats_total": len(rows),
        "scenarios": scenarios,
    }


def main() -> int:
    data = load(INPUT)
    if not data:
        result = {
            "version": 1,
            "genere_le": dt.datetime.now(dt.timezone.utc).isoformat(),
            "maximum_matchs": MAX_MATCHES,
            "maximum_par_source": 10,
            "candidats_total": 0,
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
