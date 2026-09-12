import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print("🔍 AUDITING RECENT 5-MINUTE MARKET TRADES AT T-12s ON POLYMARKET")
print("="*95)

# Query recent public trades on 5-minute BTC markets
try:
    r = requests.get("https://data-api.polymarket.com/trades?limit=50").json()
    btc_trades = [t for t in r if "Bitcoin Up or Down" in t.get("title", "")]
    print(f"Found {len(btc_trades)} recent 5m BTC market trades on Polymarket:")
    for t in btc_trades[:12]:
        dt = time.strftime("%H:%M:%S UTC", time.gmtime(t.get("timestamp", 0)))
        side = t.get("side")
        sz = t.get("size")
        px = t.get("price")
        out = t.get("outcome")
        print(f"  • [{dt}] {side:<4} {sz:<6} shares of {out:<4} @ ${px:<5} | Market: {t.get('title')}")
except Exception as e:
    print("Error:", e)

print("="*95)
