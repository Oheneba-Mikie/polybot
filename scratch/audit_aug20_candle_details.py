import requests
import json
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
slug = "btc-updown-5m-1787258400" # August 20, 20:40 - 20:45 UTC (4:40 PM - 4:45 PM ET)

print("="*90)
print(f"AUDITING THE AUGUST 20 WIPE-OUT CANDLE: {slug}")
print("="*90)

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}").json()
if r and r[0].get("markets"):
    mkt = r[0]["markets"][0]
    print("Question:", mkt.get("question"))
    print("Resolution Outcome Prices:", mkt.get("outcomePrices"))
    print("Closed:", mkt.get("closed"))

# Binance 1m candles for 20:40 - 20:45 UTC on Aug 20
ts = 1787258400 # 20:40 UTC
print("\nBinance 1m Price Breakdown:")
r_k = requests.get("https://api.binance.com/api/v3/klines", 
                   params={"symbol":"BTCUSDT", "interval":"1m", "startTime":ts*1000, "endTime":(ts+300)*1000}).json()
for k in r_k:
    dt = datetime.datetime.fromtimestamp(k[0]/1000, datetime.timezone.utc).strftime("%H:%M")
    print(f"[{dt}] Open: ${float(k[1]):.2f} | High: ${float(k[2]):.2f} | Low: ${float(k[3]):.2f} | Close: ${float(k[4]):.2f}")

print("="*90)
