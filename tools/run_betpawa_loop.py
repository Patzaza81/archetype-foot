#!/usr/bin/env python3
"""Close the ARCHETYPE -> BetPawa local loop without modifying the ticket generator.

Pipeline:
    generateur_tickets.py
        -> data/tickets.json
        -> betpawa_validation.py
        -> data/betpawa_validation.json
        -> tools/betpawa_local_runner.py
        -> visible BetPawa coupon

The generator itself is executed unchanged. This wrapper only orchestrates its
existing command-line entry point and the existing validation gateway.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "generateur_tickets.py"
VALIDATOR = ROOT / "betpawa_validation.py"
RUNNER = ROOT / "tools" / "betpawa_local_runner.py"
TICKETS = ROOT / "data" / "tickets.json"
MANIFEST = ROOT / "data" / "betpawa_validation.json"


def run(command: list[str]) -> None:
    print("$ " + " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Générateur ARCHETYPE -> validation -> coupon BetPawa local"
    )
    parser.add_argument(
        "--no-generate",
        action="store_true",
        help="ne pas relancer le générateur ; utiliser son dernier data/tickets.json",
    )
    parser.add_argument(
        "--ticket-id",
        help="ticket AX-... à préparer ; sans cette option le runner demande un choix",
    )
    parser.add_argument(
        "--click",
        action="store_true",
        help="autoriser les clics dans le navigateur après confirmation explicite",
    )
    parser.add_argument(
        "--max-tickets",
        type=int,
        default=15,
        help="nombre maximal de tickets examinés par la passerelle",
    )
    args = parser.parse_args()

    if not args.no_generate:
        run([sys.executable, str(GENERATOR)])

    if not TICKETS.is_file():
        raise SystemExit(
            "data/tickets.json est absent : le générateur n'a pas produit de sortie exploitable."
        )

    run([
        sys.executable,
        str(VALIDATOR),
        "--input", str(TICKETS),
        "--output", str(MANIFEST),
        "--max-tickets", str(args.max_tickets),
    ])

    command = [sys.executable, str(RUNNER), "--input", str(TICKETS)]
    if args.ticket_id:
        command.extend(["--ticket-id", args.ticket_id])
    if args.click:
        command.append("--click")
    return subprocess.run(command, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
