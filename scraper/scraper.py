import argparse
import asyncio
import logging
import re
import sys
from datetime import datetime

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

sys.path.append(".")  # allow running as `python scraper/scraper.py` from project root
from database.db import init_db, get_session
from database.models import Car

# --------------------------------------------------------------------------- #
# CONFIG — edit this block if PakWheels changes their markup
# --------------------------------------------------------------------------- #

BASE_SEARCH_URL = "https://www.pakwheels.com/used-cars/search/-"

SELECTORS = {
    "card": "li.classified-listing, div.search-listing, div.classified-listing-item",
    "title": "a.car-name, h3.car-name a, a[itemprop='url']",
    "price": ".price-details, .generic-green, li.price",
    "listing_link": "a.car-name, a[itemprop='url']",
    "image": "img.img-responsive, img[itemprop='image']",
    # PakWheels shows a "search-vehicle-info" <ul> with li items like
    # "2019", "45,000 km", "Petrol", "Automatic", "Lahore"
    "info_list": "ul.search-vehicle-info li, ul.vehicle-detail li",
    "load_more_button": "a.load-more, button.load-more",
}

# City -> Province lookup used to populate the "province" filter,
# since PakWheels only shows the city on the listing card.
CITY_PROVINCE_MAP = {
    "lahore": "Punjab", "faisalabad": "Punjab", "rawalpindi": "Punjab",
    "multan": "Punjab", "gujranwala": "Punjab", "sialkot": "Punjab",
    "islamabad": "Islamabad Capital Territory",
    "karachi": "Sindh", "hyderabad": "Sindh", "sukkur": "Sindh",
    "peshawar": "Khyber Pakhtunkhwa", "abbottabad": "Khyber Pakhtunkhwa",
    "mardan": "Khyber Pakhtunkhwa", "swat": "Khyber Pakhtunkhwa",
    "quetta": "Balochistan", "gwadar": "Balochistan",
}

MAX_LISTINGS_DEFAULT = 200
SCROLL_PAUSE_MS = 1200
NAV_TIMEOUT_MS = 30000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("pakwheels-scraper")


# --------------------------------------------------------------------------- #
# Parsing helpers
# --------------------------------------------------------------------------- #

def parse_price(raw: str):
    """'PKR 25.5 lacs' / 'PKR 1.2 crore' -> float rupees."""
    if not raw:
        return None
    raw = raw.lower().replace(",", "").strip()
    match = re.search(r"([\d.]+)\s*(lac|lacs|lakh|crore)?", raw)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2)
    if unit in ("lac", "lacs", "lakh"):
        value *= 100_000
    elif unit == "crore":
        value *= 10_000_000
    return value


def parse_mileage(raw: str):
    if not raw:
        return None
    digits = re.sub(r"[^\d]", "", raw)
    return int(digits) if digits else None


def parse_year(raw: str):
    match = re.search(r"(19|20)\d{2}", raw or "")
    return int(match.group(0)) if match else None


def parse_engine_cc(raw: str):
    match = re.search(r"(\d{3,5})\s*cc", (raw or "").lower())
    return int(match.group(1)) if match else None


def guess_make_model(title: str):
    """Best-effort split of 'Toyota Corolla Altis 2019' -> ('Toyota', 'Corolla')."""
    if not title:
        return None, None
    parts = title.strip().split()
    make = parts[0] if parts else None
    model_name = parts[1] if len(parts) > 1 else None
    return make, model_name


def resolve_province(city: str):
    if not city:
        return None
    return CITY_PROVINCE_MAP.get(city.strip().lower())


# --------------------------------------------------------------------------- #
# Core scraping logic
# --------------------------------------------------------------------------- #

async def autoscroll(page, max_listings: int):
    """Scroll to the bottom repeatedly so infinite-scroll cards load in,
    stopping once we have enough listings or the page stops growing."""
    previous_count = 0
    stagnant_rounds = 0

    while True:
        cards = await page.query_selector_all(SELECTORS["card"])
        count = len(cards)
        logger.info("Loaded %d listing cards so far...", count)

        if count >= max_listings:
            break
        if count == previous_count:
            stagnant_rounds += 1
            if stagnant_rounds >= 3:
                logger.info("No new cards after 3 scrolls — assuming end of results.")
                break
        else:
            stagnant_rounds = 0
        previous_count = count

        await page.mouse.wheel(0, 4000)
        try:
            await page.wait_for_load_state("networkidle", timeout=4000)
        except PlaywrightTimeoutError:
            pass
        await page.wait_for_timeout(SCROLL_PAUSE_MS)


async def extract_card(card):
    """Pull structured fields out of a single listing card. Returns dict or None."""
    try:
        title_el = await card.query_selector(SELECTORS["title"])
        title = (await title_el.inner_text()).strip() if title_el else None

        link_el = await card.query_selector(SELECTORS["listing_link"])
        href = await link_el.get_attribute("href") if link_el else None
        if href and href.startswith("/"):
            href = "https://www.pakwheels.com" + href

        if not title or not href:
            return None  # not enough to identify this listing — skip

        price_el = await card.query_selector(SELECTORS["price"])
        price_raw = (await price_el.inner_text()).strip() if price_el else None

        img_el = await card.query_selector(SELECTORS["image"])
        image_url = await img_el.get_attribute("src") if img_el else None

        info_items = await card.query_selector_all(SELECTORS["info_list"])
        info_texts = [(await el.inner_text()).strip() for el in info_items]

        year = None
        mileage = None
        fuel_type = None
        transmission = None
        city = None
        engine_cc = None

        for text in info_texts:
            low = text.lower()
            if year is None and re.search(r"^(19|20)\d{2}$", text):
                year = parse_year(text)
            elif "km" in low and mileage is None:
                mileage = parse_mileage(text)
            elif low in ("petrol", "diesel", "hybrid", "cng", "electric"):
                fuel_type = text
            elif low in ("automatic", "manual"):
                transmission = text
            elif "cc" in low and engine_cc is None:
                engine_cc = parse_engine_cc(text)
            elif city is None and text.replace(" ", "").isalpha():
                city = text

        make, model_name = guess_make_model(title)

        return {
            "title": title,
            "make": make,
            "model_name": model_name,
            "price": parse_price(price_raw),
            "year": year,
            "mileage": mileage,
            "engine_capacity": engine_cc,
            "fuel_type": fuel_type,
            "transmission": transmission,
            "registration_city": city,
            "province": resolve_province(city),
            "listing_url": href,
            "image_url": image_url,
            "posted_date": None,
        }
    except Exception as exc:  # noqa: BLE001 — one bad card should never kill the run
        logger.warning("Skipping a card due to parse error: %s", exc)
        return None


def upsert_car(session, data: dict):
    existing = session.query(Car).filter_by(listing_url=data["listing_url"]).first()
    if existing:
        for key, value in data.items():
            if value is not None:
                setattr(existing, key, value)
        existing.scraped_at = datetime.utcnow()
    else:
        session.add(Car(**data))
    session.flush()


async def run_scrape(max_listings: int = MAX_LISTINGS_DEFAULT, debug: bool = False, headless: bool = True):
    init_db()
    session = get_session()
    saved = 0
    skipped = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        )
        page = await context.new_page()
        page.set_default_navigation_timeout(NAV_TIMEOUT_MS)

        logger.info("Navigating to %s", BASE_SEARCH_URL)
        try:
            await page.goto(BASE_SEARCH_URL, wait_until="domcontentloaded")
        except PlaywrightTimeoutError:
            logger.error("Navigation timed out — check your internet/DNS connection.")
            await browser.close()
            return {"saved": 0, "skipped": 0, "error": "navigation_timeout"}

        await autoscroll(page, max_listings)

        if debug:
            html = await page.content()
            with open("scraper/debug_dump.html", "w", encoding="utf-8") as f:
                f.write(html)
            logger.info("Saved rendered HTML to scraper/debug_dump.html for selector inspection.")

        cards = await page.query_selector_all(SELECTORS["card"])
        cards = cards[:max_listings]
        logger.info("Extracting %d cards...", len(cards))

        for card in cards:
            data = await extract_card(card)
            if data is None:
                skipped += 1
                continue
            try:
                upsert_car(session, data)
                saved += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("DB upsert failed for a listing: %s", exc)
                skipped += 1

            # gentle rate limiting so we don't hammer PakWheels
            await asyncio.sleep(0.05)

        session.commit()
        session.close()
        await browser.close()

    logger.info("Scrape complete. Saved/updated: %d, Skipped: %d", saved, skipped)
    return {"saved": saved, "skipped": skipped}


def main():
    parser = argparse.ArgumentParser(description="Scrape PakWheels used-car listings.")
    parser.add_argument("--max", type=int, default=MAX_LISTINGS_DEFAULT, help="Max listings to scrape")
    parser.add_argument("--debug", action="store_true", help="Dump rendered HTML for selector debugging")
    parser.add_argument("--headed", action="store_true", help="Run browser with a visible window")
    args = parser.parse_args()

    asyncio.run(run_scrape(max_listings=args.max, debug=args.debug, headless=not args.headed))


if __name__ == "__main__":
    main()