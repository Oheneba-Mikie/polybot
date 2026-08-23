import os
import sys
import json
import time
import datetime
import requests
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST = "https://data-api.polymarket.com"
CLOB_HOST = "https://clob.polymarket.com"

print("="*100)
print("🔍 30-60 MINUTE DEEP AUDIT: WHAT HAPPENS IF WE JUST SIT IN THE BOOK WITH RESTING ORDERS?")
print("="*100)

# Fetch recent 5m BTC markets from the last 1-2 hours
now = time.time()
r = requests.get(f"{GAMMA_HOST}/events?limit=50&active=true&closed=false").json()
r_closed = requests.get(f"{GAMMA_HOST}/events?limit=50&active=false&closed=true").json()

all_events = r + r_closed
btc_markets = []

for ev in all_events:
    slug = ev.get("slug", "")
    if "btc-updown-5m" in slug or "btc" in slug.lower():
        mkts = ev.get("markets", [])
        if mkts:
            m = mkts[0]
            clob_tokens = json.loads(m.get("clobTokenIds", "[]"))
            outcomes = json.loads(m.get("outcomes", "[]"))
            if len(clob_tokens) >= 2:
                up_id = clob_tokens[0]
                dn_id = clob_tokens[1]
                if len(outcomes) >= 2 and outcomes[0].lower() not in ("up", "yes"):
                    up_id, dn_id = clob_tokens[1], clob_tokens[0]
                
                # Check resolution winner if closed
                winner = None
                prices_str = m.get("outcomePrices")
                if prices_str:
                    pxs = json.loads(prices_str)
                    if pxs and float(pxs[0]) >= 0.99: winner = "UP"
                    elif pxs and float(pxs[1]) >= 0.99: winner = "DOWN"
                
                btc_markets.append({
                    "slug": slug,
                    "title": m.get("question", slug),
                    "condition_id": m.get("conditionId"),
                    "up_id": up_id,
                    "down_id": dn_id,
                    "winner": winner
                })

# Deduplicate
seen_cids = set()
unique_markets = []
for m in btc_markets:
    if m["condition_id"] not in seen_cids:
        seen_cids.add(m["condition_id"])
        unique_markets.append(m)

print(f"Auditing trade books across {len(unique_markets)} recent 5-Minute BTC markets...\n")

total_trades_analyzed = 0
all_trades_by_market = {}

for mkt in unique_markets:
    cid = mkt["condition_id"]
    try:
        r_t = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=500", timeout=10).json()
        if r_t:
            all_trades_by_market[cid] = {
                "info": mkt,
                "trades": r_t
            }
            total_trades_analyzed += len(r_t)
    except Exception as e:
        pass

print(f"Total trade transactions retrieved: {total_trades_analyzed}\n")

# Test sitting in the book at 3 different target pairs:
# Pair A (Symmetric 50/50): Bid UP @ 0.47 + Bid DOWN @ 0.47 (Cost = $0.94, 6¢ margin)
# Pair B (Tight 50/50):     Bid UP @ 0.48 + Bid DOWN @ 0.48 (Cost = $0.96, 4¢ margin)
# Pair C (Asymmetric 80/20): Bid UP @ 0.78 + Bid DOWN @ 0.18 (Cost = $0.96, 4¢ margin)
# Pair D (Late 90/10):       Bid UP @ 0.90 + Bid DOWN @ 0.08 (Cost = $0.98, 2¢ margin)

strategies = {
    "50/50 Deep (0.47 + 0.47 = $0.94)": {"up_bid": 0.47, "dn_bid": 0.47, "cost": 0.94},
    "50/50 Standard (0.48 + 0.48 = $0.96)": {"up_bid": 0.48, "dn_bid": 0.48, "cost": 0.96},
    "Asymmetric 80/20 (0.78 + 0.18 = $0.96)": {"up_bid": 0.78, "dn_bid": 0.18, "cost": 0.96},
    "Late Squeeze (0.90 + 0.08 = $0.98)": {"up_bid": 0.90, "dn_bid": 0.08, "cost": 0.98},
}

results = {}

for strat_name, cfg in strategies.items():
    up_bid_px = cfg["up_bid"]
    dn_bid_px = cfg["dn_bid"]
    pair_cost = cfg["cost"]
    
    total_both_filled_pairs = 0
    total_only_up_filled = 0
    total_only_dn_filled = 0
    total_unmatched_losses_usd = 0.0
    total_matched_profit_usd = 0.0
    market_breakdowns = []
    
    for cid, data in all_trades_by_market.items():
        m_info = data["info"]
        trades = data["trades"]
        winner = m_info["winner"]
        
        # Track if trades sold at or below our bid prices (meaning we would get filled as a maker)
        up_filled_shares = 0.0
        dn_filled_shares = 0.0
        
        for t in trades:
            outcome = str(t.get("outcome", "")).lower()
            side = t.get("side", "") # BUY or SELL
            px = float(t.get("price") or 0)
            sz = float(t.get("size") or 0)
            
            # If someone sold (taker SELL) at or below our limit bid, our limit BUY fills!
            # Or if trade executed at price <= our bid
            if outcome in ("up", "yes") and px <= up_bid_px:
                up_filled_shares += sz
            elif outcome in ("down", "no") and px <= dn_bid_px:
                dn_filled_shares += sz
                
        # Calculate matched pairs vs unmatched single legs
        matched_pairs = min(up_filled_shares, dn_filled_shares)
        excess_up = up_filled_shares - matched_pairs
        excess_dn = dn_filled_shares - matched_pairs
        
        # PnL on matched pairs: (1.00 - pair_cost) * matched_pairs
        pnl_matched = matched_pairs * (1.00 - pair_cost)
        
        # PnL on unmatched excess legs (evaluated at final resolution):
        pnl_unmatched = 0.0
        if winner == "UP":
            pnl_unmatched += excess_up * (1.00 - up_bid_px) # UP won
            pnl_unmatched -= excess_dn * dn_bid_px          # DOWN lost
        elif winner == "DOWN":
            pnl_unmatched -= excess_up * up_bid_px          # UP lost
            pnl_unmatched += excess_dn * (1.00 - dn_bid_px) # DOWN won
            
        net_mkt_pnl = pnl_matched + pnl_unmatched
        
        market_breakdowns.append({
            "slug": m_info["slug"],
            "winner": winner,
            "up_filled": round(up_filled_shares, 2),
            "dn_filled": round(dn_filled_shares, 2),
            "matched_pairs": round(matched_pairs, 2),
            "excess_up": round(excess_up, 2),
            "excess_dn": round(excess_dn, 2),
            "matched_profit": round(pnl_matched, 4),
            "unmatched_pnl": round(pnl_unmatched, 4),
            "net_pnl": round(net_mkt_pnl, 4)
        })
        
        total_both_filled_pairs += matched_pairs
        if excess_up > 0: total_only_up_filled += excess_up
        if excess_dn > 0: total_only_dn_filled += excess_dn
        total_matched_profit_usd += pnl_matched
        total_unmatched_losses_usd += pnl_unmatched

    results[strat_name] = {
        "matched_pairs": round(total_both_filled_pairs, 2),
        "unmatched_up_shares": round(total_only_up_filled, 2),
        "unmatched_dn_shares": round(total_only_dn_filled, 2),
        "matched_profit_usd": round(total_matched_profit_usd, 4),
        "unmatched_pnl_usd": round(total_unmatched_losses_usd, 4),
        "total_net_pnl_usd": round(total_matched_profit_usd + total_unmatched_losses_usd, 4),
        "markets": market_breakdowns
    }

print("="*110)
print(f"{'STRATEGY (RESTING BIDS)':<40} | {'MATCHED PAIRS':<15} | {'UNMATCHED LEGS':<18} | {'NET P&L ($)'}")
print("="*110)
for strat, res in results.items():
    matched = f"{res['matched_pairs']:.1f} pairs (+${res['matched_profit_usd']:.2f})"
    unmatched = f"{res['unmatched_up_shares'] + res['unmatched_dn_shares']:.1f} sh ({res['unmatched_pnl_usd']:+.2f})"
    net = f"${res['total_net_pnl_usd']:+.2f}"
    print(f"{strat:<40} | {matched:<15} | {unmatched:<18} | {net}")

print("\n" + "="*110)
print("DETAILED BREAKDOWN OF INDIVIDUAL 5-MINUTE MARKETS (SAMPLE: 50/50 STANDARD $0.96):")
print("="*110)
sample_strat = results["50/50 Standard (0.48 + 0.48 = $0.96)"]["markets"]
for m in sample_strat[:8]:
    win_str = m['winner'] or 'OPEN'
    print(f"Market: {m['slug'][:30]} (Winner: {win_str:<4}) | UP Filled: {m['up_filled']:6.1f} sh | DN Filled: {m['dn_filled']:6.1f} sh | Matched: {m['matched_pairs']:6.1f} | Net: ${m['net_pnl']:+.2f}")

with open("scratch/sitting_in_book_audit.json", "w") as fp:
    json.dump(results, fp, indent=2)
