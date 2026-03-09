import os
import asyncio
from playwright.async_api import async_playwright

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send(msg):
    import requests
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# Estimate prize values based on keywords
def estimate_rrp(title):
    title = title.lower()
    if "driver" in title:
        return 500
    if "putter" in title:
        return 300
    if "wedge" in title:
        return 450
    if "bag" in title:
        return 350
    if "ball" in title:
        return 200
    if "rangefinder" in title:
        return 250
    return 200

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://mashedpotatogolfcomps.co.uk/competitions/", timeout=0)
        await page.wait_for_timeout(5000)  # wait for JS to render

        # select all competition cards
        cards = await page.query_selector_all(".competition-card")

        for card in cards:
            title = await card.query_selector(".title")
            title_text = await title.inner_text() if title else "Unknown Prize"

            price_elem = await card.query_selector(".ticket-price")
            price_text = await price_elem.inner_text() if price_elem else "£0.29"
            price = float(price_text.replace("£",""))

            sold_elem = await card.query_selector(".percentage-sold")
            sold_text = await sold_elem.inner_text() if sold_elem else "0%"
            sold_percent = float(sold_text.replace("%",""))

            # some comps show remaining tickets
            remaining_elem = await card.query_selector(".tickets-remaining")
            max_tickets = 5000
            if remaining_elem:
                remaining_text = await remaining_elem.inner_text()
                remaining = int("".join(filter(str.isdigit, remaining_text)))
                sold_tickets = max_tickets - remaining
            else:
                sold_tickets = max_tickets * (sold_percent/100)

            revenue = sold_tickets * price
            rrp = estimate_rrp(title_text)
            overlay = rrp - revenue

            # alert threshold
            if overlay > 200:
                msg = f"""🔥 Overlay Opportunity

{title_text}

Ticket price: £{price}
Sold: {sold_percent:.1f}%
Estimated revenue: £{revenue:.2f}
Prize value: £{rrp}
Overlay: £{overlay:.2f}
"""
                send(msg)

        await browser.close()

asyncio.run(main())

