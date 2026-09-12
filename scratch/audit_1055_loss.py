import requests
import json
import datetime
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_HOST  = "https://data-api.polymarket.com"
GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

# 10:55 AM - 11:00 AM ET on August 26 is 14:55 - 15:00 UTC
w_s = 1787756100 # 14:55 UTC
slug = f"btc-updown-5m-{w_s}"
user_addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8" # Proxy wallet

print("="*95)
print(f"📊 FORENSIC AUDIT: 10:55 AM - 11:00 AM ET (14:55 - 15:00 UTC) CANDLE: {slug}")
print("="*95)

# 1. Fetch our wallet's trades in this window
r_trades = requests.get(f"{DATA_HOST}/trades?user={user_addr}&limit=10").json()
print("📁 WALLET TRADES IN THIS TIMEFRAME:")
for t in r_trades:
    ts = t.get("timestamp", 0)
    dt_utc = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%H:%M:%S UTC")
    dt_et = datetime.datetime.fromtimestamp(ts - 4*3600, datetime.timezone.utc).strftime("%I:%M:%S %p ET")
    out = t.get("outcome")
    sz = float(t.get("size", 0))
    px = float(t.get("price", 0))
    side = t.get("side")
    title = t.get("title", "")
    print(f"  [{dt_et} | {dt_utc}] {side:<4} {sz:>6.2f} shares of {out:<4} @ ${px:.4f} (Cost: ${sz*px:.2f}) | Market: {title}")

# 2. Check Railway Bot logs around 14:55 - 15:00 UTC
r_state = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=4).json()
print("\n📜 RAILWAY BOT LOGS:")
for l in r_state.get("logs", [])[-25:]:
    print(f"   {l}")

# 3. Check Binance 1-minute price breakdown between 14:55 and 15:00 UTC
start_ms = w_s * 1000
r_binance = requests.get("https://api.binance.com/api/v3/klines", 
                         params={"symbol": "BTCUSDT", "interval": "1m", "startTime": start_ms, "limit": 6}).json()
print("\n📈 BINANCE 1-MINUTE PRICE PROGRESSION (Strike was $77,824.21):")
for b in r_binance:
    t_dt = datetime.datetime.fromtimestamp(b[0]/1000, datetime.timezone.utc).strftime("%H:%M UTC")
    t_et = datetime.datetime.fromtimestamp(b[0]/1000 - 4*3600, datetime.timezone.utc).strftime("%I:%M %p ET")
    o, h, l, c = float(b[1]), float(b[2]), float(b[3]), float(b[4])
    strike = 77824.21
    gap = c - strike
    print(f"   [{t_et} | {t_dt}] Open: ${o:.2f} | High: ${h:.2f} | Low: ${l:.2f} | Close: ${c:.2f} | Gap vs Strike: ${gap:+.2f}")

print("="*95)
