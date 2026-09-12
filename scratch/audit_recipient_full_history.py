import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

target_addr = "0x639f7e0b317f586b350cdcc1ceb22a2ed44e2211"
DATA_HOST = "https://data-api.polymarket.com"

print("="*95)
print(f"🔍 FULL TRANSACTION & ACTIVITY AUDIT FOR ADDRESS: {target_addr}")
print("="*95)

# 1. Fetch all Polymarket Activity records
try:
    r_act = requests.get(f"{DATA_HOST}/activity?user={target_addr}&limit=30").json()
    print(f"\n📊 Polymarket Activity Records ({len(r_act)} found):")
    for idx, a in enumerate(r_act, 1):
        dt = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(a.get("timestamp", 0)))
        typ = a.get("type", "N/A")
        side = a.get("side", "N/A")
        sz = a.get("size", "N/A")
        usdc_sz = a.get("usdcSize", "N/A")
        title = a.get("title", a.get("asset", "N/A"))
        print(f"  [{idx:02d}] {dt} | Type: {typ:<7} | Side: {side:<4} | Amount: ${str(usdc_sz):<8} | Shares: {str(sz):<8} | Market: {title}")
except Exception as e:
    print("Activity API error:", e)

# 2. Fetch Polymarket Trades
try:
    r_tr = requests.get(f"{DATA_HOST}/trades?user={target_addr}&limit=20").json()
    print(f"\n📈 Polymarket Trades on This Address ({len(r_tr)} found):")
    for idx, t in enumerate(r_tr, 1):
        dt = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(t.get("timestamp", 0)))
        side = t.get("side", "N/A")
        out = t.get("outcome", "N/A")
        sz = t.get("size", "N/A")
        px = t.get("price", "N/A")
        title = t.get("title", "N/A")
        print(f"  [{idx:02d}] {dt} | {side:<4} {str(sz):<8} sh of {out:<4} @ ${str(px):<6} | Market: {title}")
except Exception as e:
    print("Trades API error:", e)

print("="*95)
