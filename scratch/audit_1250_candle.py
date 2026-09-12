import requests
import json
import datetime
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

# Candle: 12:50 UTC - 12:55 UTC (August 25)
ts = 1787662200 # 12:50 UTC
slug = f"btc-updown-5m-{ts}"

print("="*90)
print(f"🔍 FORENSIC AUDIT OF 12:50 - 12:55 UTC CANDLE ({slug})")
print("="*90)

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()
if r and r[0].get("markets"):
    mkt = r[0]["markets"][0]
    cid = mkt.get("conditionId")
    print(f"Question: {mkt.get('question')}")
    print(f"Resolution Outcome Prices: {mkt.get('outcomePrices')}")
    print(f"Closed: {mkt.get('closed')} | Resolved: {mkt.get('resolved')}")
    
    # Query trades during this candle
    r_trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=100", timeout=5).json()
    print(f"\nTotal trades on this market: {len(r_trades)}")
    
    print("\nTrades during final 90 seconds (12:53:30 to 12:55:00 UTC):")
    candle_end = ts + 300
    for t in reversed(r_trades):
        t_sec = t.get("timestamp", 0)
        time_left = candle_end - t_sec
        dt = datetime.datetime.fromtimestamp(t_sec, datetime.timezone.utc).strftime("%H:%M:%S")
        px = float(t.get("price", 0))
        out = t.get("outcome", "")
        sz = float(t.get("size", 0))
        if 0 <= time_left <= 90:
            print(f"[{dt} | T-{time_left:.0f}s] {out:<4} | {sz:>6.2f} sh @ ${px:.4f}")

# Check Binance 1m price for this candle
print("\nBinance BTC 1m price:")
r_k = requests.get("https://api.binance.com/api/v3/klines", params={"symbol":"BTCUSDT", "interval":"1m", "startTime":ts*1000, "endTime":(ts+300)*1000}, timeout=5).json()
for k in r_k:
    dt = datetime.datetime.fromtimestamp(k[0]/1000, datetime.timezone.utc).strftime("%H:%M")
    print(f"[{dt}] Open: ${float(k[1]):.2f} | High: ${float(k[2]):.2f} | Low: ${float(k[3]):.2f} | Close: ${float(k[4]):.2f}")

print("="*90)
