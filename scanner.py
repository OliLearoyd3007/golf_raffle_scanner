import os
import asyncio
from playwright.async_api import async_playwright
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

def estimate_rrp(title):
    title = title.lower()
    if "driver" in title: return 500
    if "putter" in title: return 300
    if "wedge" in title: return 450
    if "bag" in title: return 350
    if "ball" in title: return 200
    if "rangefinder" in title: return 250
    return 200

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://mashedpotatogolfcomps.co.uk/competitions/", timeout=0)
        await page.wait_for_timeout(5000)  # wait for JS to render

        # select all competition cards
        cards = await page.query_selector_all("li.product.type-product")

        for card in cards:
            # title
            title_elem = await card.query_selector("h2.woocommerce-loop-product__title")
            title = await title_elem.inner_text() if title_elem else "Unknown Prize"

            # ticket price
            price_elem = await card.query_selector("span.woocommerce-Price-amount bdi")
            price = float((await price_elem.inner_text()).replace("£","")) if price_elem else 0.29

            # % sold
            sold_elem = await card.query_selector("span[class^='zapc-refresh-percentage']")
            sold_percent = float(await sold_elem.inner_text()) if sold_elem else 0

            # remaining tickets
            remaining_elem = await card.query_selector("span[class^='zapc-refresh-remaining']")
            remaining = int(await remaining_elem.inner_text()) if remaining_elem else None
            max_tickets = 5000
            sold_tickets = max_tickets - remaining if remaining is not None else max_tickets*(sold_percent/100)

            # overlay calculation
            rrp = estimate_rrp(title)
            revenue = sold_tickets * price
            overlay = rrp - revenue

            # alert threshold
            if overlay > 200:
                msg = f"""🔥 Overlay Opportunity

{title}

Ticket price: £{price}
Sold: {sold_percent:.1f}%
Remaining tickets: {remaining}
Estimated revenue: £{revenue:.2f}
Prize value: £{rrp}
Overlay: £{overlay:.2f}
"""
                send(msg)

        await browser.close()

asyncio.run(main())
