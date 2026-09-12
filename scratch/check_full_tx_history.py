import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

user_addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"

print("="*95)
print(f"🔍 COMPREHENSIVE ON-CHAIN & POLYMARKET API CHECK FOR: {user_addr}")
print("="*95)

# 1. Query PolygonScan free public API for recent ERC-20 transfers
url_ps = f"https://api.polygonscan.com/api?module=account&action=tokentx&address={user_addr}&startblock=0&endblock=99999999&page=1&offset=15&sort=desc"
try:
    r = requests.get(url_ps, timeout=8).json()
    status = r.get("status")
    result = r.get("result", [])
    print(f"\n📡 PolygonScan API Token Transfers ({len(result) if isinstance(result, list) else 0} found):")
    if isinstance(result, list):
        for tx in result[:10]:
            h = tx.get("hash")
            fr = tx.get("from")
            to = tx.get("to")
            val = float(tx.get("value", 0)) / (10 ** int(tx.get("tokenDecimal", 6)))
            sym = tx.get("tokenSymbol")
            ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(int(tx.get("timeStamp", 0))))
            print(f"  [{ts}] {val:.4f} {sym} | From: {fr} -> To: {to}")
            print(f"    Hash: https://polygonscan.com/tx/{h}")
    else:
        print("  PolygonScan note:", r.get("message"))
except Exception as e:
    print("PolygonScan error:", e)

# 2. Query Polymarket Relayer / Proxy Events via Data API
print("\n--- 2. POLYMARKET DATA API TRANSFERS & REDEMPTIONS ---")
try:
    r_act = requests.get(f"https://data-api.polymarket.com/activity?user={user_addr}&limit=10").json()
    for a in r_act:
        dt = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(a.get("timestamp", 0)))
        typ = a.get("type")
        amt = a.get("usdcSize") or a.get("size")
        tx = a.get("transactionHash")
        to_addr = a.get("to") or a.get("recipient")
        title = a.get("title", a.get("asset", ""))
        print(f"  [{dt}] Type: {typ:<8} | Amount: ${str(amt):<8} | TX: {tx} | Detail: {title}")
except Exception as e:
    print("Polymarket activity error:", e)

print("="*95)
