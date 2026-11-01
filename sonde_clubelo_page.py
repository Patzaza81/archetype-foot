"""Sonde : une page de classement ClubElo s'ouvre-t-elle dans un navigateur ordinaire (Playwright, sans aucun contournement) ? Écrit data/clubelo/sonde_page.txt."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

jour = sys.argv[1] if len(sys.argv) > 1 else "2026-10-31"
sortie = Path("data/clubelo/sonde_page.txt")
sortie.parent.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    nav = p.chromium.launch()
    page = nav.new_page()
    rep = page.goto(f"https://clubelo.com/{jour}", wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(4000)
    corps = page.inner_text("body")[:600].replace("\n", " | ")
    verdict = "DEFI_ANTI_ROBOT" if any(x in (page.title() + corps).lower() for x in ("just a moment", "verify you are human", "cloudflare", "challenge")) else "PAGE_NORMALE"
    sortie.write_text(f"statut http: {rep.status if rep else None}\ntitre: {page.title()}\nverdict: {verdict}\ncorps: {corps}\n", encoding="utf-8")
    nav.close()
print(sortie.read_text(encoding="utf-8"))
