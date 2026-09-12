import requests
import json
import time
import datetime
import sys
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding='utf-8')

print("="*115)
print("🔍 EXHAUSTIVE 7-DAY AUDIT: DOES THE LOSING SIDE ALWAYS DROP TO 1¢/2¢ & ARE SHARES ALWAYS AVAILABLE?")
print("="*115)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

# Sample 150 closed historical 5-minute Bitcoin markets across the past 7 days (Aug 21 - Aug 28)
now_ts = int(time.time() // 300) * 300
sample_timestamps = [now_ts - (i * 300 * 12) for i in range(1, 151)]

def audit_loser_price_and_depth(ts):
    slug = f"btc-updown-5m-{ts}"
    w_s = ts
    w_e = ts + 300
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
        if not r or not r[0].get("markets"): return None
        mkt = r[0]["markets"][0]
        cid = mkt.get("conditionId")
        q = mkt.get("question")
        out_prices = json.loads(mkt.get("outcomePrices") or "[]")
        if not out_prices or len(out_prices) < 2: return None
        
        p0 = float(out_prices[0])
        p1 = float(out_prices[1])
        if p0 == p1: return None
        winner_side = "UP" if p0 > p1 else "DOWN"
        loser_side = "DOWN" if winner_side == "UP" else "UP"
        
        # Query verified trade logs
        tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=200", timeout=4).json()
        if not tr or not isinstance(tr, list): return None
        
        winner_buys = []
        loser_buys = []
        
        for t in tr:
            trade_ts = t.get("timestamp", 0)
            if w_s <= trade_ts <= w_e:
                side = str(t.get("side", "")).upper()
                out = str(t.get("outcome", "")).upper()
                px = float(t.get("price", 0))
                sz = float(t.get("size", 0))
                offset_s = trade_ts - w_s
                
                if side == "BUY":
                    if out == winner_side:
                        winner_buys.append({"px": px, "sz": sz, "off": offset_s})
                    elif out == loser_side:
                        loser_buys.append({"px": px, "sz": sz, "off": offset_s})
                        
        min_loser_price = min([x["px"] for x in loser_buys]) if loser_buys else 1.00
        loser_shares_at_low = sum([x["sz"] for x in loser_buys if x["px"] <= 0.02]) if loser_buys else 0.0
        
        # Winner shares at ~86c (84c - 88c)
        winner_shares_at_86 = sum([x["sz"] for x in winner_buys if 0.82 <= x["px"] <= 0.88]) if winner_buys else 0.0
        winner_time_at_86 = min([x["off"] for x in winner_buys if 0.82 <= x["px"] <= 0.88]) if winner_shares_at_86 > 0 else -1
        loser_time_at_low = min([x["off"] for x in loser_buys if x["px"] <= 0.02]) if loser_shares_at_low > 0 else -1
        
        return {
            "slug": slug,
            "title": q,
            "winner": winner_side,
            "min_loser_px": min_loser_price,
            "hit_1c": min_loser_price <= 0.012,
            "hit_2c": min_loser_price <= 0.025,
            "hit_5c": min_loser_price <= 0.055,
            "loser_shares_2c": loser_shares_at_low,
            "winner_shares_86c": winner_shares_at_86,
            "winner_time_86": winner_time_at_86,
            "loser_time_low": loser_time_at_low,
            "has_both_86_and_2c": (winner_shares_at_86 > 0 and loser_shares_at_low > 0)
        }
    except Exception:
        return None

print(f"Auditing 150 historical 5m markets across the past week for loser price collapse and share depth...\n")

results = []
with ThreadPoolExecutor(max_workers=12) as executor:
    for res in executor.map(audit_loser_price_and_depth, sample_timestamps):
        if res:
            results.append(res)

total_m = len(results)
print(f"Successfully audited {total_m} verified historical 5-minute markets across 7 days.\n")

# Compute Statistics
count_hit_1c = sum(1 for r in results if r["hit_1c"])
count_hit_2c = sum(1 for r in results if r["hit_2c"])
count_hit_5c = sum(1 for r in results if r["hit_5c"])
count_never_below_10c = sum(1 for r in results if r["min_loser_px"] > 0.10)
count_both_86_and_2c = sum(1 for r in results if r["has_both_86_and_2c"])

loser_shares_list = [r["loser_shares_2c"] for r in results if r["loser_shares_2c"] > 0]
winner_shares_list = [r["winner_shares_86c"] for r in results if r["winner_shares_86c"] > 0]

avg_loser_shares_2c = (sum(loser_shares_list) / len(loser_shares_list)) if loser_shares_list else 0.0
avg_winner_shares_86 = (sum(winner_shares_list) / len(winner_shares_list)) if winner_shares_list else 0.0

print("="*115)
print("📊 7-DAY EMPIRICAL RESULTS: LOSING TOKEN PRICE COLLAPSE & SHARE DEPTH")
print("="*115)
print(f"1. Does the Losing Token drop to 1¢ (<= $0.01)?")
print(f"   • Occurred in: {count_hit_1c} / {total_m} markets ({count_hit_1c/total_m*100:.1f}%)")
print(f"   • Average Shares Available to Buy @ <= 2¢: {avg_loser_shares_2c:,.1f} shares\n")

print(f"2. Does the Losing Token drop to 2¢ (<= $0.02)?")
print(f"   • Occurred in: {count_hit_2c} / {total_m} markets ({count_hit_2c/total_m*100:.1f}%)")
print(f"   • Average Shares Available to Buy @ <= 2¢: {avg_loser_shares_2c:,.1f} shares\n")

print(f"3. Does the Losing Token drop to 5¢ (<= $0.05)?")
print(f"   • Occurred in: {count_hit_5c} / {total_m} markets ({count_hit_5c/total_m*100:.1f}%)\n")

print(f"4. Tight / Choppy Markets where Loser NEVER drops below 10¢:")
print(f"   • Occurred in: {count_never_below_10c} / {total_m} markets ({count_never_below_10c/total_m*100:.1f}%)\n")

print(f"5. Markets where BOTH 86¢ Winner AND 2¢ Loser existed in the same window:")
print(f"   • Occurred in: {count_both_86_and_2c} / {total_m} markets ({count_both_86_and_2c/total_m*100:.1f}%)")
print(f"   • Average Winning Shares Available @ 86¢: {avg_winner_shares_86:,.1f} shares")
print("="*115)

# Print a breakdown table of individual sample markets
print(f"\n{'Market Title':<45} | {'Lowest Loser Price':<20} | {'Shares @ <= 2¢':<16} | {'Winner Shares @ 86¢'}")
print("-" * 115)
for r in results[:15]:
    l_px = f"${r['min_loser_px']:.3f}"
    l_sh = f"{r['loser_shares_2c']:,.0f} sh" if r['loser_shares_2c'] > 0 else "0 sh"
    w_sh = f"{r['winner_shares_86c']:,.0f} sh" if r['winner_shares_86c'] > 0 else "0 sh"
    print(f"{r['title']:<45} | {l_px:<20} | {l_sh:<16} | {w_sh}")

print("="*115)
