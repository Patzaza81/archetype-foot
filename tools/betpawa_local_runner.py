#!/usr/bin/env python3
"""Local, visible Playwright runner: add selected ARCHETYPE markets to BetPawa.

Safety contract:
- visible persistent Chromium profile; the user signs in manually if needed;
- no credentials are read or stored by this script outside Chromium's own profile;
- only clicks an odds control when market + outcome matching is unique;
- never enters a stake and never clicks a place/confirm/submit bet control;
- dry-run is the default; --click requires a typed confirmation.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "tickets.json"
DEFAULT_PROFILE = ROOT / ".local" / "betpawa-profile"
BETPAWA_HOME = "https://www.betpawa.cm/"
URL_RE = re.compile(r"^https://(?:www\.)?betpawa\.cm/event/[A-Za-z0-9_-]+(?:\?.*)?$")
ODDS_RE = re.compile(r"^\d{1,3}[.,]\d{2}$")


class UnsafeSelection(ValueError):
    """A selection cannot be matched to one unambiguous BetPawa control."""


def normalise(value: Any) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def has_phrase(haystack: str, phrase: str) -> bool:
    """Match a normalized phrase as whole words, not as a substring."""
    return bool(re.search(r"(?<![a-z0-9])" + re.escape(normalise(phrase)) + r"(?![a-z0-9])",
                          normalise(haystack)))


def selection_target(leg: dict[str, Any]) -> tuple[list[str], list[str], str]:
    """Return market aliases, outcome aliases, and a human-readable target.

    Deliberately supports only markets with an explicit, unambiguous mapping.
    Unsupported/ambiguous labels fail closed instead of risking a wrong click.
    """
    market_raw = str(leg.get("marche") or "").lower()
    market_text = "".join(ch for ch in unicodedata.normalize("NFKD", market_raw) if not unicodedata.combining(ch))
    market = normalise(market_raw)
    home = str(leg.get("domicile") or "").strip()
    away = str(leg.get("exterieur") or "").strip()
    team = str(leg.get("journal_team") or "").strip()

    if market in {"victoire domicile", "victoire a domicile", "home win", "home"}:
        return ["1x2", "match result", "match winner", "full time result", "resultat du match"], [
            "home", "home win", "1", "domicile", "equipe a domicile", home
        ], f"Victoire domicile ({home})"
    if market in {"victoire exterieur", "victoire a l exterieur", "away win", "away"}:
        return ["1x2", "match result", "match winner", "full time result"], [
            "away", "away win", "2", "exterieur", "equipe visiteuse", away
        ], f"Victoire extérieur ({away})"
    if market in {"match nul", "nul", "draw"}:
        return ["1x2", "match result", "match winner", "full time result"], [
            "draw", "tie", "x", "nul", "match nul"
        ], "Match nul"

    if "ne perd pas" in market or "double chance" in market:
        if "12" in market or "home or away" in market:
            outcome = ["12", "home or away"]
            label = "Double chance 12"
        elif team and home and normalise(team) == normalise(home):
            outcome = ["1x", "home or draw", "home or tie", "domicile ou nul", "nul ou domicile"]
            label = f"Double chance 1X ({home})"
        elif team and away and normalise(team) == normalise(away):
            outcome = ["x2", "draw or away", "tie or away", "nul ou exterieur", "exterieur ou nul"]
            label = f"Double chance X2 ({away})"
        elif re.search(r"\b1x\b", market):
            outcome, label = ["1x", "home or draw", "home or tie"], "Double chance 1X"
        elif re.search(r"\bx2\b", market):
            outcome, label = ["x2", "draw or away", "tie or away"], "Double chance X2"
        else:
            raise UnsafeSelection(
                "Double chance ambiguë : l'équipe concernée n'est pas identifiée explicitement "
                "dans journal_team ou dans le libellé."
            )
        return ["double chance"], outcome, label

    total = re.search(r"(?:match a |total )?(moins de|plus de|under|over)\s*(\d+(?:[.,]\d+)?)", market_text)
    if total:
        direction = "under" if total.group(1) in {"moins de", "under"} else "over"
        line = total.group(2).replace(",", ".")
        direction_fr = "moins de" if direction == "under" else "plus de"
        return ["total goals", "goals over under", "over under", "total buts", "total de buts"], [
            f"{direction} {line}", f"{direction} {line.replace('.0', '')}",
            f"{direction_fr} {line}", f"{direction_fr} {line.replace('.0', '')}"
        ], f"{direction_fr} {line} buts"

    if "les deux equipes marquent" in market or "both teams to score" in market or market.startswith("btts"):
        if re.search(r"\b(non|no)\b", market):
            return ["both teams to score", "btts", "les deux equipes marquent"], [
                "no", "non", "btts no"
            ], "Les deux équipes marquent : non"
        if re.search(r"\b(oui|yes)\b", market):
            return ["both teams to score", "btts", "les deux equipes marquent"], [
                "yes", "oui", "btts yes"
            ], "Les deux équipes marquent : oui"
        raise UnsafeSelection("BTTS sans issue explicite Oui/Non.")

    if market in {"1x", "double chance 1x"}:
        return ["double chance"], ["1x", "home or draw", "home or tie", "domicile ou nul", "nul ou domicile"], "Double chance 1X"
    if market in {"x2", "double chance x2"}:
        return ["double chance"], ["x2", "draw or away", "tie or away", "nul ou exterieur", "exterieur ou nul"], "Double chance X2"
    if market in {"12", "double chance 12"}:
        return ["double chance"], ["12", "home or away"], "Double chance 12"

    raise UnsafeSelection(f"Marché non pris en charge de façon sûre : {leg.get('marche')!r}")


def load_manifest(path: Path, max_tickets: int = 15) -> dict[str, Any]:
    """Build the same validation manifest used by the website, locally."""
    from betpawa_validation import build_manifest
    data = json.loads(path.read_text(encoding="utf-8"))
    return build_manifest(data, max_tickets=max_tickets)


def list_ready_tickets(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [t for t in manifest.get("tickets", []) if t.get("status") == "READY_FOR_REVIEW"]


def resolve_ticket(manifest: dict[str, Any], ticket_id: str | None) -> dict[str, Any]:
    ready = list_ready_tickets(manifest)
    if not ready:
        raise ValueError("Aucun ticket READY_FOR_REVIEW. Aucun clic ne sera effectué.")
    if ticket_id:
        matches = [t for t in ready if str(t.get("ticket_id")) == ticket_id]
        if len(matches) != 1:
            raise ValueError(f"Ticket {ticket_id!r} absent, bloqué ou non unique.")
        return matches[0]
    if len(ready) == 1:
        return ready[0]
    print("Tickets prêts à examiner :")
    for i, ticket in enumerate(ready, 1):
        print(f"  {i}. {ticket.get('ticket_id')} | {ticket.get('scenario')} | "
              f"{ticket.get('selection_count')} sélection(s) | cote totale "
              f"{ticket.get('total_odds_snapshot')}")
    choice = input(f"Choisir un ticket (1-{len(ready)}) : ").strip()
    if not choice.isdigit() or not 1 <= int(choice) <= len(ready):
        raise ValueError("Choix invalide.")
    return ready[int(choice) - 1]


def plan_ticket(ticket: dict[str, Any]) -> list[dict[str, Any]]:
    plan = []
    for index, leg in enumerate(ticket.get("selection", []), 1):
        url = str(leg.get("betpawa_url") or "")
        if not URL_RE.fullmatch(url):
            raise UnsafeSelection(f"Sélection {index}: URL BetPawa absente ou non autorisée.")
        markets, outcomes, label = selection_target(leg)
        plan.append({
            "index": index, "url": url, "leg": leg,
            "markets": markets, "outcomes": outcomes, "label": label,
        })
    return plan


def find_odds_control(page: Any, item: dict[str, Any]) -> tuple[Any, str]:
    """Find one odds button whose ancestor context identifies both market and outcome."""
    controls = page.locator(
        "[data-test-id*='odd' i], [data-testid*='odd' i], button, [role='button']"
    )
    matches: dict[str, tuple[Any, str, int]] = {}
    for i in range(min(controls.count(), 1500)):
        control = controls.nth(i)
        try:
            if not control.is_visible() or not control.is_enabled():
                continue
            own_text = (control.inner_text(timeout=500) or "").strip()
            if not ODDS_RE.fullmatch(own_text):
                continue
            current_odds = own_text.replace(",", ".")
            market_level = None
            outcome_level = None
            for level in range(1, 9):
                parent = control.locator(f"xpath=ancestor::*[{level}]")
                if not parent.count():
                    continue
                context = parent.first.inner_text(timeout=500)
                if outcome_level is None and any(has_phrase(context, o) for o in item["outcomes"]):
                    outcome_level = level
                if market_level is None and any(has_phrase(context, m) for m in item["markets"]):
                    market_level = level
                if market_level is not None and outcome_level is not None:
                    break
            # The outcome must be identifiable in a local row, and the market
            # must be identifiable in that row or one of its wider ancestors.
            if market_level is not None and outcome_level is not None and market_level >= outcome_level:
                key = str(i)
                matches[key] = (control, current_odds, max(market_level, outcome_level))
        except Exception:
            continue
    if len(matches) != 1:
        raise UnsafeSelection(
            f"Sélection {item['index']} — {item['label']} : "
            f"{len(matches)} contrôle(s) de cote correspondent. Aucun clic pour cette sélection."
        )
    control, current_odds, _ = next(iter(matches.values()))
    return control, current_odds


def click_ticket(plan: list[dict[str, Any]], profile_dir: Path) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright absent. Installez-le avec python -m pip install playwright "
            "puis python -m playwright install chromium."
        ) from exc

    profile_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1365, "height": 900},
            locale="fr-CM",
            timezone_id="Africa/Douala",
            accept_downloads=False,
        )
        page = context.pages[0] if context.pages else context.new_page()
        try:
            page.goto(BETPAWA_HOME, wait_until="domcontentloaded", timeout=60_000)
            print("\nLe navigateur BetPawa est ouvert.")
            print("Si nécessaire, connectez-vous vous-même dans ce navigateur. "
                  "Ne communiquez jamais votre mot de passe à ce script.")
            input("Quand BetPawa est prêt, revenez ici et appuyez sur Entrée… ")

            for item in plan:
                page.goto(item["url"], wait_until="domcontentloaded", timeout=60_000)
                try:
                    page.wait_for_load_state("networkidle", timeout=10_000)
                except Exception:
                    pass
                page.wait_for_timeout(1200)
                try:
                    control, current_odds = find_odds_control(page, item)
                except Exception as exc:
                    print(f"ARRÊT SANS CLIC POUR CETTE SÉLECTION : {exc}")
                    print("Le navigateur reste ouvert pour inspecter le coupon.")
                    input("Appuyez sur Entrée pour fermer le navigateur… ")
                    return 2
                source_odds = item["leg"].get("cote")
                print(f"\n{item['index']}/{len(plan)} — {item['leg'].get('domicile')} — "
                      f"{item['leg'].get('exterieur')}")
                print(f"Marché ARCHETYPE : {item['leg'].get('marche')}")
                print(f"Cible UI : {item['label']} | cote source {source_odds} | "
                      f"cote BetPawa visible {current_odds}")
                odds_changed = False
                if source_odds is not None:
                    try:
                        odds_changed = abs(float(source_odds) - float(current_odds)) >= 0.005
                    except (TypeError, ValueError):
                        pass
                if odds_changed:
                    print("ATTENTION : la cote a changé depuis la génération.")
                    accept = input("Pour accepter explicitement la cote actuelle, tapez CLICK CURRENT ODDS ; sinon STOP : ").strip()
                    if accept != "CLICK CURRENT ODDS":
                        print("Sélection ignorée. Le navigateur reste ouvert pour inspection.")
                        input("Appuyez sur Entrée pour fermer le navigateur… ")
                        return 2
                control.click(timeout=5000)
                page.wait_for_timeout(700)
                print("Clic effectué. Vérifiez visuellement que cette sélection figure dans le coupon.")
                if item["index"] < len(plan):
                    answer = input("Coupon correct ? Entrée = continuer ; tapez STOP pour interrompre : ").strip()
                    if answer.upper() == "STOP":
                        print("Arrêt demandé. Le navigateur reste ouvert pour inspection.")
                        input("Appuyez sur Entrée pour fermer le navigateur… ")
                        return 2
            print("\nToutes les sélections prévues ont été cliquées.")
            print("Le coupon reste ouvert : vérifiez équipes, marchés, cotes et nombre de sélections.")
            print("Aucune mise n'a été saisie et aucun pari n'a été confirmé.")
            input("Appuyez sur Entrée pour fermer le navigateur (le coupon n'est pas soumis)… ")
            return 0
        finally:
            context.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Fichier source data/tickets.json")
    parser.add_argument("--ticket-id", help="ID exact du ticket READY_FOR_REVIEW")
    parser.add_argument("--max-tickets", type=int, default=15)
    parser.add_argument("--profile-dir", type=Path, default=DEFAULT_PROFILE,
                        help="Profil Chromium persistant local (ne pas partager ni versionner)")
    parser.add_argument("--click", action="store_true",
                        help="Autoriser les clics après prévisualisation et confirmation explicite")
    args = parser.parse_args(argv)

    try:
        manifest = load_manifest(args.input, args.max_tickets)
        ticket = resolve_ticket(manifest, args.ticket_id)
        plan = plan_ticket(ticket)
    except (OSError, json.JSONDecodeError, ValueError, UnsafeSelection, ImportError) as exc:
        print(f"ARRÊT SANS CLIC : {exc}", file=sys.stderr)
        return 2

    print("\nARCHETYPE → BETPAWA : PRÉVISUALISATION")
    print(f"Ticket : {ticket.get('ticket_id')} | scénario : {ticket.get('scenario')}")
    print(f"Sélections : {len(plan)} | cote totale source : {ticket.get('total_odds_snapshot')}")
    for item in plan:
        leg = item["leg"]
        print(f" {item['index']}. {leg.get('domicile')} — {leg.get('exterieur')} | "
              f"{leg.get('marche')} | cible : {item['label']} | cote source : {leg.get('cote')}")
    print("\nSécurité : le script ne saisit aucune mise et ne clique jamais sur Confirmer/Placer le pari.")
    if not args.click:
        print("\nMode prévisualisation uniquement. Aucun navigateur n'a été piloté et aucun clic n'a été effectué.")
        print("Après vérification, relancez avec --click pour activer les clics.")
        return 0

    confirmation = input("\nPour autoriser les clics, tapez exactement CLICK SELECTIONS : ").strip()
    if confirmation != "CLICK SELECTIONS":
        print("Confirmation non reçue. Aucun clic effectué.")
        return 1
    try:
        return click_ticket(plan, args.profile_dir)
    except Exception as exc:
        print(f"ARRÊT : {exc}", file=sys.stderr)
        print("Vérifiez le coupon manuellement avant toute autre action.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
