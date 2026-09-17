import requests
import json
import time
import datetime
import sys
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

# Let's audit 100 historical 5-minute crypto markets across past days
now = int(time.time())
cur_w = (now // 300) * 300
windows = [cur_w - (i * 300) for i in range(1, 80)]

print("=" * 90)
print("DEEP AUDIT: BUYING 0.98 IN A WAVE & WAITING FOR 0.01 ON THE LOSING SIDE")
print("=" * 90)

def audit_market(w_s):
    # Try BTC first, then ETH
    for coin in ["btc", "eth"]:
        slug = f"{coin}-updown-5m-{w_s}"
        try:
            r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
            if not r or not r[0].get("markets"):
                continue
            m = r[0]["markets"][0]
            cid = m.get("conditionId")
            out_prices = json.loads(m.get("outcomePrices") or "[]")
            outcomes = json.loads(m.get("outcomes") or "[]")
            if not cid or len(out_prices) < 2:
                continue

            # Fetch trades for this window
            trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=2000", timeout=4).json()
            if not isinstance(trades, list) or len(trades) < 10:
                continue

            parsed = []
            for t in trades:
                tr_ts = t.get("timestamp") or t.get("matchTime")
                if isinstance(tr_ts, str):
                    try:
                        tr_ts = datetime.datetime.fromisoformat(tr_ts.replace("Z", "+00:00")).timestamp() if "T" in tr_ts else float(tr_ts)
                    except:
                        tr_ts = 0
                if tr_ts and tr_ts > 1e11:
                    tr_ts /= 1000.0

                if w_s <= tr_ts <= w_s + 300:
                    parsed.append({
                        "ts": tr_ts,
                        "sec": int(tr_ts - w_s),
                        "price": float(t.get("price", 0)),
                        "size": float(t.get("size", 0)),
                        "side": str(t.get("side", "")).upper(),
                        "outcome": str(t.get("outcome", "")).upper()
                    })

            if not parsed:
                continue

            parsed.sort(key=lambda x: x["ts"])

            # Who ultimately won?
            p0 = float(out_prices[0])
            p1 = float(out_prices[1])
            if p0 == p1:
                continue
            final_winner = outcomes[0].upper() if p0 > p1 else outcomes[1].upper()
            final_loser  = outcomes[1].upper() if final_winner == outcomes[0].upper() else outcomes[0].upper()

            # Find all times a wave pushed any token to >= 0.98
            wave_98_trades = [t for t in parsed if t["price"] >= 0.975 and t["side"] == "BUY"]
            if not wave_98_trades:
                continue

            first_98 = wave_98_trades[0]
            token_surged = first_98["outcome"]
            token_crushed = outcomes[1].upper() if token_surged == outcomes[0].upper() else outcomes[0].upper()

            # Did the token that hit 0.98 actually win? Or did it REVERSE?
            did_reverse = (token_surged != final_winner)

            # How many shares were traded/available at 0.98 (0.975 - 0.985)?
            shares_at_98 = sum(t["size"] for t in parsed if t["outcome"] == token_surged and 0.975 <= t["price"] <= 0.985)
            shares_at_99 = sum(t["size"] for t in parsed if t["outcome"] == token_surged and 0.985 < t["price"] <= 0.995)

            # Now, AFTER the 0.98 hit, did the other token drop to 0.01 (<= 0.015)?
            subsequent_other_trades = [t for t in parsed if t["ts"] >= first_98["ts"] and t["outcome"] == token_crushed]
            
            subsequent_01_trades = [t for t in subsequent_other_trades if t["price"] <= 0.015]
            subsequent_02_trades = [t for t in subsequent_other_trades if 0.015 < t["price"] <= 0.025]

            shares_other_at_01 = sum(t["size"] for t in subsequent_01_trades)
            shares_other_at_02 = sum(t["size"] for t in subsequent_02_trades)
            min_other_price = min([t["price"] for t in subsequent_other_trades]) if subsequent_other_trades else 1.0

            # Time lag between first 0.98 and first 0.01
            time_to_01 = None
            if subsequent_01_trades:
                time_to_01 = round(subsequent_01_trades[0]["ts"] - first_98["ts"], 1)

            return {
                "slug": slug,
                "token_surged": token_surged,
                "first_98_sec": first_98["sec"],
                "did_reverse": did_reverse,
                "shares_at_98": shares_at_98,
                "shares_at_99": shares_at_99,
                "min_other_price": min_other_price,
                "hit_01_after_98": len(subsequent_01_trades) > 0,
                "shares_other_at_01": shares_other_at_01,
                "hit_02_after_98": len(subsequent_02_trades) > 0,
                "shares_other_at_02": shares_other_at_02,
                "time_to_01": time_to_01,
                "total_trades": len(parsed)
            }
        except Exception as e:
            continue
    return None

print("Auditing historical markets for 0.98 waves and subsequent 0.01 availability...")
with ThreadPoolExecutor(max_workers=8) as ex:
    results = [r for r in ex.map(audit_market, windows) if r is not None]

print(f"\nAudit complete! Found {len(results)} markets where price reached >= 0.98 in a wave.\n")

if not results:
    sys.exit(0)

# Statistics
count_total = len(results)
count_hit_01 = sum(1 for r in results if r["hit_01_after_98"])
count_hit_02_only = sum(1 for r in results if not r["hit_01_after_98"] and r["hit_02_after_98"])
count_never_below_02 = sum(1 for r in results if not r["hit_01_after_98"] and not r["hit_02_after_98"])
count_reversals = sum(1 for r in results if r["did_reverse"])

shares_98_list = [r["shares_at_98"] for r in results if r["shares_at_98"] > 0]
shares_01_list = [r["shares_other_at_01"] for r in results if r["shares_other_at_01"] > 0]
shares_02_list = [r["shares_other_at_02"] for r in results if r["shares_other_at_02"] > 0]

avg_98_shares = sum(shares_98_list) / len(shares_98_list) if shares_98_list else 0
avg_01_shares = sum(shares_01_list) / len(shares_01_list) if shares_01_list else 0
avg_02_shares = sum(shares_02_list) / len(shares_02_list) if shares_02_list else 0

times_to_01 = [r["time_to_01"] for r in results if r["time_to_01"] is not None]
avg_time_to_01 = sum(times_to_01) / len(times_to_01) if times_to_01 else 0

print("=" * 90)
print("📊 KEY EMPIRICAL FINDINGS:")
print("=" * 90)
print(f"Total Wave Markets Examined (where price hit >= 0.98): {count_total}")
print(f"\n1. SHARE DEPTH AVAILABLE TO BUY AT $0.98:")
print(f"   • Average shares traded at $0.98: {avg_98_shares:,.1f} shares")
print(f"   • Typical range: {min(shares_98_list) if shares_98_list else 0:,.0f} sh to {max(shares_98_list) if shares_98_list else 0:,.0f} sh")

print(f"\n2. DOES THE OTHER SIDE DROP TO 0.01 AFTER YOU BUY 0.98?")
print(f"   • Drops to $0.01:      {count_hit_01} / {count_total} markets ({count_hit_01/count_total*100:.1f}%)")
print(f"   • Stops at $0.02:       {count_hit_02_only} / {count_total} markets ({count_hit_02_only/count_total*100:.1f}%)")
print(f"   • Never drops to $0.02: {count_never_below_02} / {count_total} markets ({count_never_below_02/count_total*100:.1f}%)")

print(f"\n3. HOW MANY SHARES ARE AVAILABLE AT $0.01 (THE BOTTLE-NECK):")
print(f"   • When $0.01 is available, average shares filled at $0.01: {avg_01_shares:,.1f} shares")
print(f"   • When $0.02 is available, average shares filled at $0.02: {avg_02_shares:,.1f} shares")
print(f"   • Average wait time from 0.98 to 0.01 arrival: {avg_time_to_01:.1f} seconds")

print(f"\n4. FATAL REVERSAL RISK (The Unhedged Trap):")
print(f"   • Wave hit 0.98 but then CRASHED/REVERSED: {count_reversals} / {count_total} markets ({count_reversals/count_total*100:.1f}%)")
print("=" * 90)

print("\nSAMPLE DETAILED LOG OF 10 MARKETS:")
print(f"{'Market':<25} | {'Hit 0.98':<10} | {'98 Shares':<10} | {'Dropped to 1c?':<14} | {'1c Shares':<10} | {'Reversed?'}")
print("-" * 90)
for r in results[:10]:
    rev_str = "⚠️ YES (LOST)" if r["did_reverse"] else "NO (Won)"
    hit_1c_str = f"YES ({r['time_to_01']}s)" if r["hit_01_after_98"] else f"NO (min ${r['min_other_price']:.2f})"
    print(f"{r['slug'][-20:]:<25} | T+{r['first_98_sec']:03d}s     | {r['shares_at_98']:>8,.0f} sh | {hit_1c_str:<14} | {r['shares_other_at_01']:>8,.0f} sh | {rev_str}")
