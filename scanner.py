import requests
from bs4 import BeautifulSoup
import os
import re

URL = "https://mashedpotatogolfcomps.co.uk/competitions"

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send(msg):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    requests.post(url,data={
        "chat_id":CHAT_ID,
        "text":msg
    })


# rough prize value detection
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

    if "golf balls" in title:
        return 200

    if "rangefinder" in title:
        return 250

    return 200


page = requests.get(URL)

soup = BeautifulSoup(page.text,"html.parser")

cards = soup.find_all("div")

alerts = []

for card in cards:

    text = card.get_text(" ", strip=True)

    if "£" in text and "%" in text:

        try:

            price_match = re.search(r"£([0-9\.]+)",text)
            percent_match = re.search(r"([0-9]+)%",text)

            if not price_match or not percent_match:
                continue

            price = float(price_match.group(1))
            sold_percent = float(percent_match.group(1))

            title = text[:80]

            rrp = estimate_rrp(title)

            max_tickets = 5000

            sold = max_tickets * (sold_percent/100)

            revenue = sold * price

            overlay = rrp - revenue

            if overlay > 200:

                alerts.append(
f"""🔥 Overlay Opportunity

{title}

Ticket price: £{price}
Sold: {sold_percent}%

Estimated revenue: £{round(revenue,2)}
Prize value: £{rrp}

Overlay: £{round(overlay,2)}
"""
                )

        except:
            pass


for a in alerts:
    send(a)

