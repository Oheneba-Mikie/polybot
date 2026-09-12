import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

user_addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
DATA_HOST = "https://data-api.polymarket.com"
CLOB_HOST = "https://clob.polymarket.com"

print("="*95)
print(f"📜 COMPREHENSIVE OFFICIAL POLYMARKET API LEDGER AUDIT FOR: {user_addr}")
print("="*95)

# 1. Full Activity History (Trades, Transfers, Redemptions)
print("\n--- 1. OFFICIAL ACTIVITY LEDGER (LATEST 20 EVENTS) ---")
try:
    r_act = requests.get(f"{DATA_HOST}/activity?user={user_addr}&limit=20").json()
    if not r_act:
        print("  No activity records found.")
    for idx, a in enumerate(r_act, 1):
        dt = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(a.get("timestamp", 0)))
        typ = a.get("type", "N/A")
        side = a.get("side", "N/A")
        sz = a.get("size", "N/A")
        usdc_sz = a.get("usdcSize", "N/A")
        price = a.get("price", "N/A")
        title = a.get("title", a.get("asset", "N/A"))
        tx_hash = a.get("transactionHash", "N/A")
        print(f"  [{idx:02d}] {dt} | Type: {typ:<6} | Side: {side:<4} | Shares: {str(sz):<8} | USDC: ${str(usdc_sz):<8} | Price: ${str(price):<6} | {title}")
except Exception as e:
    print(f"  Activity API Error: {e}")

# 2. Full Trade History
print("\n--- 2. OFFICIAL TRADES LEDGER (LATEST 10 TRADES) ---")
try:
    r_tr = requests.get(f"{DATA_HOST}/trades?user={user_addr}&limit=10").json()
    if not r_tr:
        print("  No trades found.")
    for idx, t in enumerate(r_tr, 1):
        dt = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(t.get("timestamp", 0)))
        side = t.get("side", "N/A")
        out = t.get("outcome", "N/A")
        sz = t.get("size", "N/A")
        px = t.get("price", "N/A")
        title = t.get("title", "N/A")
        status = t.get("status", "MATCHED")
        print(f"  [{idx:02d}] {dt} | {side:<4} {str(sz):<8} sh of {out:<4} @ ${str(px):<6} | Status: {status:<7} | {title}")
except Exception as e:
    print(f"  Trades API Error: {e}")

# 3. Active Open Orders on CLOB
print("\n--- 3. ACTIVE OPEN ORDERS ON ORDER BOOK ---")
try:
    # Query public open orders endpoint if available
    r_orders = requests.get(f"{CLOB_HOST}/orders", params={"maker_address": user_addr}).json()
    print(f"  Open Orders Response: {r_orders}")
except Exception as e:
    print(f"  Open Orders query: {e}")

print("="*95)
