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

def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

history = {}
if Path(CSV_FILE).exists():
    with open(CSV_FILE, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            history[row["title"]] = {"sold": float(row["sold"]), "time": float(row["timestamp"])}

def estimate_rrp(title):
    t = title.lower()
    if "driver" in t: return 500
    if "putter" in t: return 300
    if "wedge" in t: return 450
    if "bag" in t: return 350
    if "ball" in t: return 200
    if "rangefinder" in t: return 250
    return 200

def alert_threshold(rrp):
    return rrp * 0.4  # only alert if overlay > 40% of prize

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        page = await browser.new_page()
        await page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "font", "media"] else route.continue_())

        for page_num in range(1, 3):  # first 2 pages
            url = f"https://mashedpotatogolfcomps.co.uk/competitions/" if page_num == 1 else f"https://mashedpotatogolfcomps.co.uk/competitions/page/{page_num}/"
            await page.goto(url, timeout=0)
            await page.wait_for_selector("li.product")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1500)
            cards = page.locator("li.product.type-product, li.swiper-slide")
            count = await cards.count()

            for i in range(count):
                card = cards.nth(i)
                try:
                    title = (await card.locator("h2.woocommerce-loop-product__title").inner_text()).strip()
                    if "instant win" in title.lower(): 
                        continue

                    price = float((await card.locator("span.woocommerce-Price-amount bdi").inner_text()).replace("£",""))
                    sold_percent_elem = card.locator("span[class^='zapc-refresh-percentage']")
                    sold_percent = float(await sold_percent_elem.inner_text()) if await sold_percent_elem.count() > 0 else 0
                    remaining_elem = card.locator("span[class^='zapc-refresh-remaining']")
                    remaining = int(await remaining_elem.inner_text()) if await remaining_elem.count() > 0 else None
                    sold_tickets = MAX_TICKETS - remaining if remaining else MAX_TICKETS*(sold_percent/100)

                    countdown = card.locator("div.zapc-countdown")
                    draw_in_seconds = 0
                    if await countdown.count() > 0:
                        days = int(await countdown.locator(".time-value--day").inner_text() or 0)
                        hours = int(await countdown.locator(".time-value--hour").inner_text() or 0)
                        mins = int(await countdown.locator(".time-value--min").inner_text() or 0)
                        secs = int(await countdown.locator(".time-value--sec").inner_text() or 0)
                        draw_in_seconds = days*86400 + hours*3600 + mins*60 + secs

                    now = time.time()
                    predicted_sold = sold_tickets
                    if title in history:
                        last = history[title]
                        delta_time = now - last["time"]
                        delta_sold = sold_tickets - last["sold"]
                        if delta_time > 0:
                            rate_per_sec = delta_sold / delta_time
                            predicted_sold = sold_tickets + rate_per_sec * draw_in_seconds
                            if draw_in_seconds < 3600: predicted_sold *= 1.35
                            elif draw_in_seconds < 7200: predicted_sold *= 1.2
                            elif draw_in_seconds < 14400: predicted_sold *= 1.1
                    predicted_sold = min(MAX_TICKETS, predicted_sold)

                    rrp = estimate_rrp(title)
                    revenue = predicted_sold * price
                    overlay = rrp - revenue
                    ev = (rrp / predicted_sold) - price
                    threshold = alert_threshold(rrp)

                    if 0 < draw_in_seconds <= ALERT_WINDOW and overlay > threshold and ev > 0:
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

                    history[title] = {"sold": sold_tickets, "time": now}

                except Exception as e:
                    print("Skipping card due to error:", e)

        # Save history
        with open(CSV_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["title","sold","timestamp"])
            writer.writeheader()
            for t,v in history.items():
                writer.writerow({"title":t,"sold":v["sold"],"timestamp":v["time"]})

        await browser.close()

asyncio.run(main())
