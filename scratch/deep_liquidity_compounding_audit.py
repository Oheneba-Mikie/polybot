import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*105)
print("🔍 EMPIRICAL LIQUIDITY, COMPOUNDING & SPEED AUDIT: T-12s EXECUTION")
print("="*105)

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

# 1. Probe current active 5m market order book depth & liquidity
print("1. PROBING ACTIVE 5-MINUTE MARKET ORDER BOOKS FOR LIQUIDITY DEPTH:")
try:
    r = requests.get(f"{GAMMA_HOST}/events?limit=10&active=true&tag_slug=bitcoin", timeout=5).json()
    btc_5m = [e for e in r if "btc-updown-5m" in e.get("slug", "")]
    
    if not btc_5m:
        # Fallback to recent closed/active events
        r2 = requests.get(f"{GAMMA_HOST}/events?limit=25&tag_slug=bitcoin", timeout=5).json()
        btc_5m = [e for e in r2 if "btc-updown-5m" in e.get("slug", "")][:5]
        
    print(f"Found {len(btc_5m)} 5-minute market events to audit for order book liquidity:")
    
    for e in btc_5m:
        slug = e.get("slug")
        title = e.get("title")
        markets = e.get("markets", [])
        if not markets: continue
        m = markets[0]
        clob_ids = json.loads(m.get("clobTokenIds") or "[]")
        if len(clob_ids) < 2: continue
        
        up_id, dn_id = clob_ids[0], clob_ids[1]
        
        # Probe UP and DOWN book depth
        for s_name, tid in [("UP", up_id), ("DOWN", dn_id)]:
            try:
                b_res = requests.get(f"{CLOB_HOST}/book", params={"token_id": tid}, timeout=3).json()
                bids = b_res.get("bids", [])
                asks = b_res.get("asks", [])
                
                sorted_asks = sorted(asks, key=lambda x: float(x["price"]))
                total_ask_shares_under_98 = sum(float(a["size"]) for a in sorted_asks if float(a["price"]) <= 0.985)
                total_ask_dollars_under_98 = sum(float(a["size"]) * float(a["price"]) for a in sorted_asks if float(a["price"]) <= 0.985)
                
                best_ask = sorted_asks[0]["price"] if sorted_asks else "N/A"
                best_bid = max([float(b["price"]) for b in bids]) if bids else "N/A"
                
                print(f"  • {s_name:<4} Book: Best Bid ${best_bid} | Best Ask ${best_ask} | Liquidity <= 98.5¢: {total_ask_shares_under_98:.1f} sh (${total_ask_dollars_under_98:.2f} USDC)")
            except Exception as ex_b:
                print(f"  • {s_name} Book probe error:", ex_b)
                
except Exception as ex:
    print("Gamma probe error:", ex)

# 2. Compounding Simulation at T-12s
print("\n" + "="*105)
print("2. COMPOUNDING SIMULATION ($5 STARTING BALANCE AT 4.5% NET GAIN PER WIN):")
print("="*105)

bal = 5.00
trades_per_day = 15
days = 10
avg_net_roi = 0.045 # 4.5% net per win (e.g. buy @ 0.957 -> $1.00 payout)

print(f"{'Day':<5} | {'Start Balance':<15} | {'Trades/Day':<12} | {'Daily Net Profit':<18} | {'Ending Balance'}")
print("-" * 75)

for d in range(1, days + 1):
    start_b = bal
    for _ in range(trades_per_day):
        # Compound 90% of balance per trade (Phase 1)
        stake = round(bal * 0.90, 2)
        profit = round(stake * avg_net_roi, 2)
        bal = round(bal + profit, 2)
    daily_gain = bal - start_b
    print(f"Day {d:<2} | ${start_b:<14.2f} | {trades_per_day:<12} | +${daily_gain:<16.2f} | ${bal:<12.2f}")

print("="*105)
