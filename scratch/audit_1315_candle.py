import requests
import json
import datetime
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

print("="*95)
print(f"📊 FORENSIC AUDIT OF THE 13:15 - 13:20 UTC CANDLE (btc-updown-5m-1787750100)")
print("="*95)

# 1. Fetch Railway Bot logs
r_state = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=4).json()
print("📜 RECENT RAILWAY BOT LOGS:")
for l in r_state.get("logs", [])[-20:]:
    print(f"   {l}")

# 2. Audit 13:15-13:20 candle on Polymarket
slug = "btc-updown-5m-1787750100"
r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}").json()
if r_evt and r_evt[0].get("markets"):
    mkt = r_evt[0]["markets"][0]
    q = mkt.get("question")
    prices = json.loads(mkt.get("outcomePrices") or "[]")
    tids = json.loads(mkt.get("clobTokenIds", "[]"))
    up_id, dn_id = tids[0], tids[1]
    
    r_up = requests.get(f"{CLOB_HOST}/book?token_id={up_id}").json()
    r_dn = requests.get(f"{CLOB_HOST}/book?token_id={dn_id}").json()
    
    up_bids = [float(b["price"]) for b in r_up.get("bids", [])]
    up_asks = [float(a["price"]) for a in r_up.get("asks", [])]
    dn_bids = [float(b["price"]) for b in r_dn.get("bids", [])]
    dn_asks = [float(a["price"]) for a in r_dn.get("asks", [])]
    
    best_up_bid = max(up_bids) if up_bids else 0.0
    best_up_ask = min(up_asks) if up_asks else None
    best_dn_bid = max(dn_bids) if dn_bids else 0.0
    best_dn_ask = min(dn_asks) if dn_asks else None
    
    print(f"\n📁 13:15 - 13:20 UTC | Slug: {slug}")
    print(f"   Question: {q}")
    print(f"   Outcome Prices: {prices}")
    print(f"   🟢 UP Token:   Top Bid: ${best_up_bid:.4f} | Best Ask: ${best_up_ask if best_up_ask is not None else 0.0:.4f} ({len(up_asks)} asks on book)")
    print(f"   🔴 DOWN Token: Top Bid: ${best_dn_bid:.4f} | Best Ask: ${best_dn_ask if best_dn_ask is not None else 0.0:.4f} ({len(dn_asks)} asks on book)")

# 3. Check Binance 1m price movement between 13:15 and 13:20
start_ms = 1787750100 * 1000
r_binance = requests.get("https://api.binance.com/api/v3/klines", 
                         params={"symbol": "BTCUSDT", "interval": "1m", "startTime": start_ms, "limit": 6}).json()
print("\n📈 BINANCE 1-MINUTE PRICE BREAKDOWN (13:15 - 13:20 UTC):")
for b in r_binance:
    t_dt = datetime.datetime.fromtimestamp(b[0]/1000, datetime.timezone.utc).strftime("%H:%M UTC")
    o, h, l, c = float(b[1]), float(b[2]), float(b[3]), float(b[4])
    print(f"   [{t_dt}] Open: ${o:.2f} | High: ${h:.2f} | Low: ${l:.2f} | Close: ${c:.2f} | Move: ${c-o:+.2f}")

print("="*95)
