import requests
import json
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

# The 12:15 UTC candle (1787487300)
ts = 1787487300
slug = f"btc-updown-5m-{ts}"

print("="*90)
print(f"📊 FORENSIC AUDIT OF CANDLE: {slug} (8:15 AM - 8:20 AM ET)")
print("="*90)

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()
if not r or not r[0].get("markets"):
    print("Market not found!")
    sys.exit(0)

mkt = r[0]["markets"][0]
cid = mkt.get("conditionId")
title = mkt.get("question")
outcome_prices = json.loads(mkt.get("outcomePrices", "[]"))

print(f"Question:            {title}")
print(f"Condition ID:        {cid}")
print(f"Final Resolv Prices: {outcome_prices}")
if outcome_prices:
    up_res = float(outcome_prices[0])
    dn_res = float(outcome_prices[1]) if len(outcome_prices) > 1 else 0.0
    winner = "UP (1.00)" if up_res == 1.0 else ("DOWN (1.00)" if dn_res == 1.0 else "Unresolved / Split")
    print(f"🏆 Final Resolution: {winner}")

print("\n" + "-"*90)
print("📜 CHRONOLOGICAL TRADES AROUND 12:15 - 12:20 UTC:")
print("-"*90)

r_trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=150", timeout=5).json()
trades = sorted(r_trades, key=lambda x: x.get("timestamp", 0))

for t in trades:
    ts_sec = t.get("timestamp", 0)
    dt = datetime.datetime.fromtimestamp(ts_sec, datetime.timezone.utc).strftime("%H:%M:%S")
    side = t.get("outcome", "")
    px = float(t.get("price", 0))
    sz = float(t.get("size", 0))
    side_type = t.get("side", "")
    note = ""
    if px >= 0.85 and side == "Up":
        note = "<- UP High"
    elif px <= 0.80 and side == "Up":
        note = "<- UP Dip / Dump"
    print(f"[{dt}] {side:<6} | ${px:<7.4f} | {sz:<10.2f} shares | {side_type:<4} {note}")

# Check Binance 1-minute klines
try:
    r_binance = requests.get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1787487300000&endTime=1787487600000", timeout=5).json()
    print("\n" + "="*90)
    print("📈 BINANCE BTC 1-MINUTE CANDLES (12:15 - 12:20 UTC):")
    print("="*90)
    for k in r_binance:
        k_time = datetime.datetime.fromtimestamp(k[0]/1000, datetime.timezone.utc).strftime("%H:%M")
        o, h, l, c = float(k[1]), float(k[2]), float(k[3]), float(k[4])
        print(f"[{k_time} UTC] Open: ${o:.2f} | High: ${h:.2f} | Low: ${l:.2f} | Close: ${c:.2f} | Net: {c-o:+.2f}")
except Exception as e:
    print("Binance check error:", e)

print("="*90)
