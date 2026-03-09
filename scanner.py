import os
import asyncio
import csv
import time
from pathlib import Path
from playwright.async_api import async_playwright
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

CSV_FILE = "ticket_history.csv"

ALERT_WINDOW = 1800  # 30 minutes
MAX_TICKETS = 5000

# -----------------------
# Telegram sender
# -----------------------

def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": msg
    })


# -----------------------
# Prize value estimator
# -----------------------

def estimate_rrp(title):

    t = title.lower()

    if "driver" in t:
        return 500
    if "putter" in t:
        return 300
    if "wedge" in t:
        return 450
    if "bag" in t:
        return 350
    if "ball" in t:
        return 200
    if "rangefinder" in t:
        return 250

    return 200


# -----------------------
# Overlay alert threshold
# -----------------------

def alert_threshold(rrp):
    return rrp * 0.4


# -----------------------
# Load ticket history
# -----------------------

history = {}

if Path(CSV_FILE).exists():

    with open(CSV_FILE, newline="") as f:

        reader = csv.DictReader(f)

        for row in reader:
            history[row["title"]] = {
                "sold": float(row["sold"]),
                "time": float(row["timestamp"])
            }


# -----------------------
# Main scraper
# -----------------------

async def main():

    async with async_playwright() as p:

        browser = await p.chromium.launch()

        page = await browser.new_page()

        pages_to_scan = 2
        all_cards = []

        for page_num in range(1, pages_to_scan + 1):

            if page_num == 1:
                url = "https://mashedpotatogolfcomps.co.uk/competitions/"
            else:
                url = f"https://mashedpotatogolfcomps.co.uk/competitions/page/{page_num}/"

            await page.goto(url, timeout=0)

            await page.wait_for_selector("li.product")

            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(3000)

            cards = await page.query_selector_all(
                "li.product.type-product, li.swiper-slide"
            )

            all_cards.extend(cards)

        seen_ids = set()
        new_history = []

        for card in all_cards:

            product_id = await card.get_attribute("data-product_id")

            if product_id and product_id in seen_ids:
                continue

            if product_id:
                seen_ids.add(product_id)

            title_elem = await card.query_selector(
                "h2.woocommerce-loop-product__title"
            )

            if not title_elem:
                continue

            title = await title_elem.inner_text()

            if "instant win" in title.lower():
                continue

            price_elem = await card.query_selector(
                "span.woocommerce-Price-amount bdi"
            )

            if not price_elem:
                continue

            price = float((await price_elem.inner_text()).replace("£", ""))

            sold_elem = await card.query_selector(
                "span[class^='zapc-refresh-percentage']"
            )

            sold_percent = float(await sold_elem.inner_text()) if sold_elem else 0

            remaining_elem = await card.query_selector(
                "span[class^='zapc-refresh-remaining']"
            )

            remaining = int(await remaining_elem.inner_text()) if remaining_elem else None

            sold_tickets = (
                MAX_TICKETS - remaining
                if remaining is not None
                else MAX_TICKETS * (sold_percent / 100)
            )

            countdown = await card.query_selector("div.zapc-countdown")

            draw_in_seconds = 0

            if countdown:

                days_elem = await countdown.query_selector(".time-value--day")
                hours_elem = await countdown.query_selector(".time-value--hour")
                mins_elem = await countdown.query_selector(".time-value--min")
                secs_elem = await countdown.query_selector(".time-value--sec")

                days = int(await days_elem.inner_text()) if days_elem else 0
                hours = int(await hours_elem.inner_text()) if hours_elem else 0
                mins = int(await mins_elem.inner_text()) if mins_elem else 0
                secs = int(await secs_elem.inner_text()) if secs_elem else 0

                draw_in_seconds = (
                    days * 86400 +
                    hours * 3600 +
                    mins * 60 +
                    secs
                )

            now = time.time()

            predicted_sold = sold_tickets

            if title in history:

                last = history[title]

                delta_time = now - last["time"]
                delta_sold = sold_tickets - last["sold"]

                if delta_time > 0:

                    rate_per_sec = delta_sold / delta_time

                    predicted_sold = sold_tickets + rate_per_sec * draw_in_seconds

                    if draw_in_seconds < 3600:
                        predicted_sold *= 1.35
                    elif draw_in_seconds < 7200:
                        predicted_sold *= 1.2
                    elif draw_in_seconds < 14400:
                        predicted_sold *= 1.1

            predicted_sold = min(MAX_TICKETS, predicted_sold)

            rrp = estimate_rrp(title)

            revenue = predicted_sold * price

            overlay = rrp - revenue

            ev = (rrp / predicted_sold) - price

            threshold = alert_threshold(rrp)

            alert = False

            if 0 < draw_in_seconds <= ALERT_WINDOW:

                if overlay > threshold and ev > 0:
                    alert = True

            if alert:

                msg = f"""🔥 Overlay Opportunity

{title}

Ticket price: £{price}
Sold: {sold_percent:.1f}%

Predicted tickets sold: {predicted_sold:.0f}

Prize value: £{rrp}
Predicted overlay: £{overlay:.2f}

Expected Value per ticket: £{ev:.3f}

Time remaining: {draw_in_seconds//3600}h {(draw_in_seconds%3600)//60}m
"""

                send(msg)

            new_history.append({
                "title": title,
                "sold": sold_tickets,
                "timestamp": now
            })

        with open(CSV_FILE, "w", newline="") as f:

            writer = csv.DictWriter(
                f,
                fieldnames=["title", "sold", "timestamp"]
            )

            writer.writeheader()
            writer.writerows(new_history)

        await browser.close()


asyncio.run(main())
