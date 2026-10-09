"""Live BetPawa UI smoke tests.

The selection test clicks exactly one public odds control in a temporary,
unauthenticated browser session and verifies that the betslip is no longer
empty. It never enters a stake, logs in, or submits a bet. A passing CI test
proves the public UI path only; it does not control a user's own browser.
"""
import re

import pytest
from playwright.sync_api import sync_playwright, expect

BASE = "https://www.betpawa.cm"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


def new_page(browser):
    page = browser.new_page(
        locale="fr-CM",
        timezone_id="Africa/Douala",
        viewport={"width": 390, "height": 844},
    )
    page.set_default_timeout(12_000)
    return page


def goto_ok(page, url):
    response = page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    assert response is not None and response.status < 500, (
        f"{url} returned HTTP {response.status if response else 'no response'}"
    )


def test_booking_code_controls_are_visible(browser):
    """Check the existing-code form without submitting a code."""
    page = new_page(browser)
    try:
        goto_ok(page, BASE + "/search")
        code = page.locator("#bookingCode")
        expect(code).to_be_visible()
        expect(code).to_have_attribute("maxlength", "7")
        expect(code).to_have_attribute("data-test-id", "bet-booking-code-input")
        form = code.locator("xpath=ancestor::form[1]")
        if form.count():
            expect(form.locator("button, input[type='submit']").first).to_be_visible()
        else:
            expect(code.locator("xpath=..").locator("button").first).to_be_visible()
    finally:
        page.close()


def test_match_search_controls_used_by_archetype_are_available(browser):
    """Check search activation and text entry without choosing a suggestion."""
    page = new_page(browser)
    try:
        goto_ok(page, BASE + "/events?categoryId=2&marketId=1X2")
        search_trigger = page.locator("[aria-label*='earch' i]").first
        expect(search_trigger).to_be_visible()
        search_trigger.click()
        fields = page.locator("input[type='text'], input[type='search'], input:not([type])")
        match_field = None
        for i in range(fields.count()):
            candidate = fields.nth(i)
            if candidate.is_visible() and candidate.get_attribute("id") != "bookingCode":
                match_field = candidate
                break
        assert match_field is not None, "No visible match-search input found after activating search"
        match_field.fill("Barcelona")
        expect(match_field).to_have_value("Barcelona")
        suggestions = page.locator("[data-test-id='search-suggestions']")
        suggestions.wait_for(state="visible", timeout=8_000)
        assert suggestions.locator("li, [role='option']").count() > 0, (
            "Search opened but returned no match suggestions for the smoke-test query"
        )
    finally:
        page.close()


def test_one_odds_click_adds_selection_to_betslip_without_betting(browser):
    """Click one visible odds control and verify a non-empty betslip.

    This is deliberately a single selection in a disposable, unauthenticated
    CI browser. No stake is entered and no bet/confirm/place button is clicked.
    """
    page = new_page(browser)
    try:
        goto_ok(page, BASE + "/events?categoryId=2&marketId=1X2")

        # Let the SPA finish rendering live event cards and market prices.
        page.wait_for_load_state("networkidle", timeout=15_000)
        page.wait_for_timeout(2_000)

        body_before = page.locator("body").inner_text(timeout=8_000)
        assert re.search(r"betslip is empty|coupon est vide|coupon est vide", body_before, re.I), (
            "Could not confirm the starting betslip is empty; refusing to click an odds control."
        )

        # BetPawa's exact CSS classes may change. Prefer explicit test IDs,
        # then accessible button-like controls with a decimal odds-only label.
        candidates = page.locator(
            "[data-test-id*='odd' i], [data-testid*='odd' i], "
            "button, [role='button']"
        )
        target = None
        target_text = None
        for i in range(min(candidates.count(), 800)):
            item = candidates.nth(i)
            if not item.is_visible() or not item.is_enabled():
                continue
            label = (item.inner_text(timeout=1_000) or "").strip()
            if re.fullmatch(r"\d{1,3}[.,]\d{2}", label):
                target = item
                target_text = label
                break

        assert target is not None, (
            "No visible odds-only control found on the public 1X2 page. "
            "BetPawa may have changed its UI or blocked automated access; inspect the run artifact/logs."
        )

        target.click()
        page.wait_for_timeout(1_500)
        body_after = page.locator("body").inner_text(timeout=8_000)
        assert not re.search(r"betslip is empty|coupon est vide", body_after, re.I), (
            f"Clicked odds {target_text}, but the page still reports an empty betslip."
        )

        # Also require the clicked price to be visible after the action.
        assert target_text in body_after, (
            f"Odds {target_text} were clicked, but could not verify the price remains visible."
        )
        # Safety invariant: the script never looks up or clicks a stake/place-bet control.
    finally:
        page.close()
