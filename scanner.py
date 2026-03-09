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

# -----------------------
# Telegram helper
# -----------------------
def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# -----------------------
# Estimate prize RRP
# -----------------------
def estimate_rrp(title):
    title = title.lower()
    if "driver" in title: return 500
    if "putter" in title: return 300
    if "wedge" in title: return 450
    if "bag" in title: return 350
    if "ball" in title: return 200
    if "rangefinder" in title: return 250
    return 200

# -----------------------
# Dynamic overlay threshold based on RRP
# -----------------------
def alert_threshold(rrp):
    # Alert if predicted overlay > 40% of RRP
    return rrp * 0.4

# -----------------------
# Load previous ticket history
# -----------------------
history = {}
if Path(CSV_FILE).exists():
    with open(CSV_FILE, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            history[row["title"]] = {"sold": float(row["sold"]), "time": float(row["timestamp"])}

# -----------------------
# Main scraper
# -----------------------
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://mashedpotatogolfcomps.co.uk/competitions/", timeout=0)
        await page.wait_for_timeout(5000)  # wait for JS to render

        cards = await page.query_selector_all("li.product.type-product")
        new_history = []

        for card in cards:
            # -----------------------
            # Prize title
            # -----------------------
            title_elem = await card.query_selector("h2.woocommerce-loop-product__title")
            title = await title_elem.inner_text() if title_elem else "Unknown Prize"

            # -----------------------
            # Ticket price
            # -----------------------
            price_elem = await card.query_selector("span.woocommerce-Price-amount bdi")
            price = float((await price_elem.inner_text()).replace("£","")) if price_elem else 0.29

            # -----------------------
            # % sold
            # -----------------------
            sold_elem = await card.query_selector("span[class^='zapc-refresh-percentage']")
            sold_percent = float(await sold_elem.inner_text()) if sold_elem else 0

            # -----------------------
            # Remaining tickets
            # -----------------------
            remaining_elem = await card.query_selector("span[class^='zap
