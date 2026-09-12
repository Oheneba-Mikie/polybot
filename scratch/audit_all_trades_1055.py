import requests
import json
import datetime
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

DATA_HOST  = "https://data-api.polymarket.com"
GAMMA_HOST = "https://gamma-api.polymarket.com"

w_s = 1787756100 # 10:55 AM - 11:00 AM ET (14:55 - 15:00 UTC)
slug = f"btc-updown-5m-{w_s}"

print("="*95)
print(f"📊 FULL ON-CHAIN TRADE LOGS: 10:55 AM - 11:00 AM ET ({slug})")
print("="*95)

r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}").json()
if r_evt and r_evt[0].get("markets"):
    mkt = r_evt[0]["markets"][0]
    cid = mkt.get("conditionId")
    q = mkt.get("question")
    
    # Fetch ALL trades that executed on this candle
    r_tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=200").json()
    
    print(f"Candle: {q}")
    print(f"Total Trades Recorded on the Book: {len(r_tr)}\n")
    print(f"{'Time (ET)':<14} | {'Time (UTC)':<14} | {'Side':<5} | {'Outcome':<6} | {'Price':<8} | {'Shares':<10} | {'USDC Value':<10}")
    print("-" * 80)
    
    for t in sorted(r_tr, key=lambda x: x.get("timestamp", 0)):
        ts = t.get("timestamp", 0)
        dt_utc = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%H:%M:%S")
        dt_et = datetime.datetime.fromtimestamp(ts - 4*3600, datetime.timezone.utc).strftime("%I:%M:%S %p")
        out = str(t.get("outcome", "")).upper()
        sz = float(t.get("size", 0))
        px = float(t.get("price", 0))
        side = str(t.get("side", "")).upper()
        val = sz * px
        
        print(f"{dt_et:<14} | {dt_utc:<14} | {side:<5} | {out:<6} | ${px:<7.4f} | {sz:>8.2f} sh | ${val:>8.2f}")

print("="*95)
