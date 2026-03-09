import requests
from bs4 import BeautifulSoup
import os

URL = "https://mashedpotatogolfcomps.co.uk/competitions"

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

rrp_lookup = {
"putter":300,
"wedge":450,
"staff bag":450,
"driver":500,
"golf balls":200
}

def send(msg):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    requests.post(url,data={
        "chat_id":CHAT_ID,
        "text":msg
    })

page = requests.get(URL)

soup = BeautifulSoup(page.text,"html.parser")

cards = soup.find_all("div",class_="competition-card")

for c in cards:

    title = c.text.lower()

    price = 0.29
    sold_percent = 5

    for key in rrp_lookup:

        if key in title:

            rrp = rrp_lookup[key]

            revenue = 5000*(sold_percent/100)*price

            overlay = rrp - revenue

            if overlay > 200:

                send(f"""
Overlay Opportunity!

{title}

Estimated overlay £{round(overlay,2)}

Ticket price £{price}
""")
