import os
import asyncio
import csv
import time
from datetime import datetime, timezone
from pathlib import Path
from playwright.async_api import async_playwright
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CSV_FILE = "ticket_history.csv"

# Telegram helper
def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# Prize value estimation
def estimate_rrp(title):
    title = title.lower()
    if "driver" in title: return 500
    if "putter" in title: return 300
    if "wedge" in title: return 450
    if "bag" in title: return 350
    if "ball" in title: return 200
    if "rangefinder" in title: return 250
    return 200

# Load previous ticket history
history = {}
if Path(CSV_FILE).exists():
    with open(CSV_FILE, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            history[row["title"]] = {"sold": float(row["sold"]), "time": float(row["timestamp"])}

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://mashedpotatogolfcomps.co.uk/competitions/", timeout=0)
        await page.wait_for_timeout(5000)

        cards = await page.query_selector_all("li.product.type-product")
        new_history = []

        for card in cards:
            # Prize title
            title_elem = await card.query_selector("h2.woocommerce-loop-product__title")
            title = await title_elem.inner_text() if title_elem else "Unknown Prize"

            # Ticket price
            price_elem = await card.query_selector("span.woocommerce-Price-amount bdi")
            price = float((await price_elem.inner_text()).replace("£","")) if price_elem else 0.29

            # % sold
            sold_elem = await card.query_selector("span[class^='zapc-refresh-percentage']")
            sold_percent = float(await sold_elem.inner_text()) if sold_elem else 0

            # Remaining tickets
            remaining_elem = await card.query_selector("span[class^='zapc-refresh-remaining']")
            remaining = int(await remaining_elem.inner_text()) if remaining_elem else None
            max_tickets = 5000
            sold_tickets = max_tickets - remaining if remaining is not None else max_tickets*(sold_percent/100)

            # Draw time
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
                draw_in_seconds = days*86400 + hours*3600 + mins*60 + secs

            now = time.time()
            predicted_sold = sold_tickets

            # Predict sales velocity
            if title in history:
                last = history[title]
                delta_time = now - last["time"]
                delta_sold = sold_tickets - last["sold"]
                if delta_time > 0:
                    rate_per_sec = delta_sold / delta_time
                    predicted_sold = min(max_tickets, sold_tickets + rate_per_sec * draw_in_seconds)

            # Overlay calculation
            rrp = estimate_rrp(title)
            revenue = predicted_sold * price
            overlay = rrp - revenue

            # Alert only close to ending (e.g., last 1 hour = 3600s)
            if overlay > 200 and draw_in_seconds <= 3600:
                msg = f"""🔥 Overlay Opportunity (Predicted)

{title}

Ticket price: £{price}
Sold: {sold_percent:.1f}%
Predicted tickets sold at draw: {predicted_sold:.0f}
Estimated revenue: £{revenue:.2f}
Prize value: £{rrp}
Predicted overlay: £{overlay:.2f}
Time remaining: {draw_in_seconds//3600}h {(draw_in_seconds%3600)//60}m
"""
                send(msg)

            new_history.append({"title": title, "sold": sold_tickets, "timestamp": now})

        # Update history
        with open(CSV_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["title","sold","timestamp"])
            writer.writeheader()
            writer.writerows(new_history)

        await browser.close()

asyncio.run(main())
