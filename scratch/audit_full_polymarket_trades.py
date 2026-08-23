import os
import sys
import json
import time
import datetime
import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv("scalper_bailout_deploy/.env")

DATA_HOST = "https://data-api.polymarket.com"
GAMMA_HOST = "https://gamma-api.polymarket.com"
POLYMARKET_ADDRESS = os.getenv("POLYMARKET_ADDRESS", "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8")

print("="*100)
print(f"🔍 COMPLETE LIVE AUDIT OF POLYMARKET WALLET ACTIVITY: {POLYMARKET_ADDRESS}")
print("="*100)

# 1. Fetch current open positions
r_pos = requests.get(f"{DATA_HOST}/positions?user={POLYMARKET_ADDRESS}&sizeThreshold=0.01", timeout=10).json()
print(f"\n📊 CURRENT OPEN POSITIONS (Shares currently in wallet):")
active_shares_found = False
for p in r_pos:
    sz = float(p.get("size", 0))
    val = float(p.get("currentValue", 0))
    if val > 0.05 or sz > 0.5:
        active_shares_found = True
        print(f"  • Market: {p.get('title')} | Outcome: {p.get('outcome')} | Shares: {sz:.4f} | Value: ${val:.2f}")

if not active_shares_found:
    print("  • No active open shares held right now (Wallet is 100% in cash/redeemed).")

# 2. Fetch all activity logs for today
r_act = requests.get(f"{DATA_HOST}/activity?user={POLYMARKET_ADDRESS}&limit=50", timeout=10).json()
print(f"\n📜 ALL TRADES & REDEMPTIONS TODAY (Chronological Audit):")
print(f"{'#':<3} | {'DATE & TIME (UTC)':<19} | {'TYPE':<6} | {'SIDE':<5} | {'PRICE':<6} | {'SHARES':<8} | {'USDC':<8} | {'MARKET TITLE'}")
print("="*100)

# Filter for today's activities (Aug 22)
today_activities = []
for a in r_act:
    ts = a.get("timestamp", 0)
    dt = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
    if dt.day == 22 and dt.month == 8 and dt.year == 2026:
        today_activities.append(a)

today_activities = sorted(today_activities, key=lambda x: x.get("timestamp", 0))

for i, a in enumerate(today_activities):
    ts = a.get("timestamp", 0)
    dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    a_type = a.get("type", "")
    side = a.get("side", "")
    px = float(a.get("price") or 0)
    sz = float(a.get("size") or 0)
    usdc = float(a.get("usdcSize") or (px * sz))
    title = a.get("title", "")
    print(f"{i+1:<3} | {dt_str:<19} | {a_type:<6} | {side:<5} | ${px:<5.2f} | {sz:<8.2f} | ${usdc:<8.2f} | {title}")

# 3. Group by market to see Buy vs Sell vs Resolution
print("\n" + "="*100)
print("🔎 MARKET-BY-MARKET BREAKDOWN: (DID WE SELL OR WAIT FOR RESOLUTION?)")
print("="*100)

from collections import defaultdict
grouped = defaultdict(list)
for a in today_activities:
    title = a.get("title", "")
    grouped[title].append(a)

for mkt_title, acts in grouped.items():
    print(f"\n📌 Market: {mkt_title}")
    has_buy = False
    has_sell = False
    has_redeem = False
    buy_time = None
    buy_px = 0
    sell_time = None
    sell_px = 0
    redeem_val = 0
    
    for a in acts:
        t = a.get("type")
        s = a.get("side")
        ts = a.get("timestamp", 0)
        dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%H:%M:%S")
        if t == "TRADE" and s == "BUY":
            has_buy = True
            buy_time = dt_str
            buy_px = float(a.get("price", 0))
            print(f"   🟢 BOUGHT at {dt_str} @ ${buy_px:.2f} ({float(a.get('size', 0)):.2f} shares for ${float(a.get('usdcSize', 0)):.2f})")
        elif t == "TRADE" and s == "SELL":
            has_sell = True
            sell_time = dt_str
            sell_px = float(a.get("price", 0))
            print(f"   ⚡ SOLD at {dt_str} @ ${sell_px:.2f} ({float(a.get('size', 0)):.2f} shares for ${float(a.get('usdcSize', 0)):.2f})")
        elif t == "REDEEM":
            has_redeem = True
            redeem_val = float(a.get("usdcSize", 0))
            print(f"   🏆 REDEEMED at {dt_str} for ${redeem_val:.2f} ($1.00 payout)")
            
    if has_buy and has_sell:
        print(f"   👉 RESULT: Instant Scalp! Bought @ ${buy_px:.2f} -> Sold @ ${sell_px:.2f} before resolution.")
    elif has_buy and has_redeem:
        print(f"   👉 RESULT: Held to Expiration! Market resolved and paid out $1.00.")
    elif has_buy and not has_sell and not has_redeem:
        print(f"   👉 RESULT: Currently Active / In Progress.")

print("="*100)
