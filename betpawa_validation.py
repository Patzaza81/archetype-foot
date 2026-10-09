"""Validation gateway ARCHETYPE -> BetPawa.

This module is deliberately isolated from the ticket generator and from the
prediction engines. It prepares a deterministic, auditable validation manifest.
It does NOT submit or confirm wagers.

Input can be either:
- a list of ticket dictionaries;
- {"tickets": [...]};
- {"pool": [...]} (each pool item becomes a one-leg candidate).

The manifest is safe for a manual final-validation workflow:
GENERATED -> CHECKED -> READY_FOR_REVIEW -> USER_VALIDATED / REJECTED / EXPIRED.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
MAX_TICKETS_PER_DAY = 15
ALLOWED_STATUSES = {
    "GENERATED", "CHECKED", "READY_FOR_REVIEW",
    "USER_VALIDATED", "REJECTED", "EXPIRED",
}
URL_RE = re.compile(r"^https://(?:www\.)?betpawa\.cm/event/[A-Za-z0-9_-]+(?:\?.*)?$")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> float | None:
    try:
        x = float(value)
        return x if x == x and abs(x) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _leg_key(leg: dict[str, Any]) -> str:
    explicit = _text(leg.get("cle_match"))
    if explicit:
        return explicit
    date = _text(leg.get("date"))
    home = _text(leg.get("domicile")).lower()
    away = _text(leg.get("exterieur")).lower()
    market = _text(leg.get("marche")).lower()
    return "|".join((date, home, away, market))


def _ticket_id(ticket: dict[str, Any], index: int) -> str:
    supplied = _text(ticket.get("ticket_id"))
    if supplied:
        return supplied
    payload = {
        "index": index,
        "scenario": ticket.get("scenario"),
        "selection": [
            {
                "cle_match": _leg_key(x),
                "marche": _text(x.get("marche")),
                "cote": _num(x.get("cote")),
            }
            for x in ticket.get("selection", [])
            if isinstance(x, dict)
        ],
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:12].upper()
    return f"AX-{digest}"


def _extract_tickets(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("tickets", "scenarios", "propositions"):
        value = data.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    # Current generator exposes a pool. Do not alter it: turn each candidate
    # into a one-leg review item only for the validation UI.
    pool = data.get("pool")
    if isinstance(pool, list):
        return [{"scenario": "POOL_CANDIDATE", "selection": [x]}
                for x in pool if isinstance(x, dict)]
    return []


def _normalise_selection(ticket: dict[str, Any]) -> list[dict[str, Any]]:
    selection = ticket.get("selection")
    if not isinstance(selection, list):
        return []
    result = []
    for leg in selection:
        if not isinstance(leg, dict):
            continue
        result.append({
            "cle_match": _leg_key(leg),
            "date": _text(leg.get("date")),
            "heure": _text(leg.get("heure_cameroun") or leg.get("heure")),
            "competition": _text(leg.get("competition")),
            "domicile": _text(leg.get("domicile")),
            "exterieur": _text(leg.get("exterieur")),
            "marche": _text(leg.get("marche")),
            "cote": _num(leg.get("cote")),
            "betpawa_url": _text(leg.get("betpawa_url")),
        })
    return result


def validate_ticket(ticket: dict[str, Any], index: int) -> dict[str, Any]:
    selection = _normalise_selection(ticket)
    errors: list[str] = []
    warnings: list[str] = []

    if not selection:
        errors.append("NO_SELECTION")
    if len(selection) > 15:
        errors.append("TOO_MANY_LEGS")

    keys = [x["cle_match"] for x in selection]
    if len(keys) != len(set(keys)):
        errors.append("DUPLICATE_MATCH")

    for i, leg in enumerate(selection, 1):
        if not leg["domicile"] or not leg["exterieur"]:
            errors.append(f"LEG_{i}_MISSING_TEAMS")
        if not leg["marche"]:
            errors.append(f"LEG_{i}_MISSING_MARKET")
        if leg["cote"] is None or leg["cote"] <= 1:
            errors.append(f"LEG_{i}_INVALID_ODDS")
        if not URL_RE.match(leg["betpawa_url"]):
            errors.append(f"LEG_{i}_INVALID_BETPAWA_URL")

    odds = 1.0
    odds_complete = bool(selection)
    for leg in selection:
        if leg["cote"] is None:
            odds_complete = False
        else:
            odds *= leg["cote"]

    if not odds_complete:
        odds = None
        warnings.append("TOTAL_ODDS_NOT_CALCULABLE")

    expected = _num(ticket.get("cote_totale"))
    if expected is None and isinstance(ticket.get("metrics"), dict):
        expected = _num(ticket["metrics"].get("cote_totale"))
    if expected is not None and odds is not None and abs(expected - odds) > 0.02:
        errors.append("TOTAL_ODDS_MISMATCH")

    status = "READY_FOR_REVIEW" if not errors else "REJECTED"
    return {
        "ticket_id": _ticket_id(ticket, index),
        "scenario": _text(ticket.get("scenario")) or "UNSPECIFIED",
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "selection_count": len(selection),
        "total_odds_snapshot": round(odds, 4) if odds is not None else None,
        "source_total_odds": expected,
        "selection": selection,
        "errors": errors,
        "warnings": warnings,
        "human_validation_required": True,
        "submission_automated": False,
    }


def build_manifest(data: Any, max_tickets: int = MAX_TICKETS_PER_DAY) -> dict[str, Any]:
    raw = _extract_tickets(data)
    if max_tickets < 1:
        raise ValueError("max_tickets must be >= 1")

    checked = [validate_ticket(t, i) for i, t in enumerate(raw[:min(max_tickets, MAX_TICKETS_PER_DAY)], 1)]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "max_tickets_per_day": MAX_TICKETS_PER_DAY,
        "tickets_requested": len(raw),
        "tickets_checked": len(checked),
        "tickets_ready": sum(x["status"] == "READY_FOR_REVIEW" for x in checked),
        "tickets_rejected": sum(x["status"] == "REJECTED" for x in checked),
        "workflow": [
            "GENERATED", "CHECKED", "READY_FOR_REVIEW",
            "USER_VALIDATED", "REJECTED", "EXPIRED",
        ],
        "manual_final_validation_required": True,
        "submission_automated": False,
        "tickets": checked,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/tickets.json")
    parser.add_argument("--output", default="data/betpawa_validation.json")
    parser.add_argument("--max-tickets", type=int, default=MAX_TICKETS_PER_DAY)
    args = parser.parse_args()

    source = Path(args.input)
    destination = Path(args.output)
    data = json.loads(source.read_text(encoding="utf-8"))
    manifest = build_manifest(data, args.max_tickets)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"BetPawa validation: {manifest['tickets_ready']} prêts / "
        f"{manifest['tickets_rejected']} rejetés / "
        f"{manifest['tickets_checked']} contrôlés"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
