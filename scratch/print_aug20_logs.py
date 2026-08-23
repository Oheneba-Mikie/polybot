import os
import json
import requests
import datetime
from dotenv import load_dotenv

load_dotenv()

ADDRESS = os.getenv("POLYMARKET_ADDRESS", "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8")

print(f"Fetching raw trade logs for wallet: {ADDRESS}")

# 1. Fetch from data-api activity
r_act = requests.get(f"https://data-api.polymarket.com/activity?user={ADDRESS}&limit=200", timeout=15)
acts = r_act.json()

# 2. Fetch from data-api trades
r_trades = requests.get(f"https://data-api.polymarket.com/trades?user={ADDRESS}&limit=200", timeout=15)
trades_data = r_trades.json()

print(f"Fetched {len(acts)} activities, {len(trades_data)} trade records.\n")

# Filter trades for August 20, 2026
aug20_acts = []
for a in acts:
    ts = a.get("timestamp", 0)
    dt = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
    if dt.strftime("%Y-%m-%d") == "2026-08-20":
        aug20_acts.append((dt, a))

aug20_acts.sort(key=lambda x: x[0])

print("="*120)
print("AUGUST 20, 2026 — OFFICIAL POLYMARKET ON-CHAIN ACTIVITY LOGS (CHRONOLOGICAL)")
print("="*120)

for dt, a in aug20_acts:
    t_type = a.get("type")
    side = a.get("side", "-")
    outcome = a.get("outcome", "-")
    price = float(a.get("price") or 0)
    shares = float(a.get("size") or 0)
    usdc = float(a.get("usdcSize") or 0)
    title = a.get("title", "")
    tx_hash = a.get("transactionHash", "") or a.get("id", "")
    
    if t_type == "TRADE":
        print(f"[{dt.strftime('%H:%M:%S')} UTC] TRADE  | {side:<4} | {outcome:<4} | Price: ${price:.3f} | Shares: {shares:6.2f} | USDC: ${usdc:6.2f} | Tx: {tx_hash[:16]}... | {title[:40]}")
    elif t_type == "REDEEM":
        print(f"[{dt.strftime('%H:%M:%S')} UTC] REDEEM |  --- | {outcome:<4} | Payout: ${usdc:.2f} (Shares: {shares:.2f})           | Tx: {tx_hash[:16]}... | {title[:40]}")

with open("scratch/aug20_raw_logs.json", "w") as f:
    json.dump([a[1] for a in aug20_acts], f, indent=2)
