"""Read-only live smoke tests for BetPawa's public UI.

These tests never sign in, add selections, create a coupon, or submit a bet.
They verify only whether the public browser controls used by ARCHETYPE remain
available. BetPawa may change its UI or block automated traffic.
"""
import os
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


def test_booking_code_controls_are_visible(browser):
    """Check the existing-code loading form without submitting a code."""
    page = new_page(browser)
    try:
        response = page.goto(BASE + "/search", wait_until="domcontentloaded", timeout=45_000)
        assert response is not None and response.status < 500, (
            f"BetPawa /search returned HTTP {response.status if response else 'no response'}"
        )
        code = page.locator("#bookingCode")
        expect(code).to_be_visible()
        expect(code).to_have_attribute("placeholder", "Enter booking code")
        expect(page.get_by_text("Load Betslip", exact=True)).to_be_visible()
    finally:
        page.close()


def test_match_search_controls_used_by_archtype_are_available(browser):
    """Check search activation and text entry; deliberately do not select a match."""
    page = new_page(browser)
    try:
        response = page.goto(
            BASE + "/events?categoryId=2&marketId=1X2",
            wait_until="domcontentloaded",
            timeout=45_000,
        )
        assert response is not None and response.status < 500, (
            f"BetPawa events returned HTTP {response.status if response else 'no response'}"
        )
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
        # Observe whether the current suggestion locator exists; do not click any suggestion.
        suggestions = page.locator("[data-test-id='search-suggestions']")
        suggestions.wait_for(state="visible", timeout=8_000)
        assert suggestions.locator("li, [role='option']").count() > 0, (
            "Search opened but returned no match suggestions for the smoke-test query"
        )
    finally:
        page.close()
