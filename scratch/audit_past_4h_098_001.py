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

# Past 4 hours = 4 * 3600 = 14400 seconds = 48 five-minute windows
now = int(time.time())
cur_w = (now // 300) * 300
windows = [cur_w - (i * 300) for i in range(1, 49)] # 48 closed candles in past 4h

print(f"Auditing Past 4 Hours: {len(windows)} 5-minute windows from {datetime.datetime.utcfromtimestamp(windows[-1])} UTC to {datetime.datetime.utcfromtimestamp(windows[0])} UTC")

def audit_candle(item):
    coin, w_s = item
    slug = f"{coin}-updown-5m-{w_s}"
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
        if not r or not r[0].get("markets"):
            return None
        m = r[0]["markets"][0]
        cid = m.get("conditionId")
        out_prices = json.loads(m.get("outcomePrices") or "[]")
        outcomes = json.loads(m.get("outcomes") or "[]")
        clob_tokens = json.loads(m.get("clobTokenIds") or "[]")
        if not cid or len(out_prices) < 2 or len(outcomes) < 2:
            return None

        trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=2000", timeout=4).json()
        if not isinstance(trades, list) or len(trades) < 5:
            return None

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

            if w_s - 10 <= tr_ts <= w_s + 310:
                parsed.append({
                    "ts": tr_ts,
                    "sec": int(tr_ts - w_s),
                    "price": float(t.get("price", 0)),
                    "size": float(t.get("size", 0)),
                    "side": str(t.get("side", "")).upper(),
                    "outcome": str(t.get("outcome", "")).upper()
                })

        if not parsed:
            return None

        parsed.sort(key=lambda x: x["ts"])

        # Determine winner
        p0 = float(out_prices[0])
        p1 = float(out_prices[1])
        winner = outcomes[0].upper() if p0 > p1 else outcomes[1].upper()

        # Check trades at ~0.98 (0.975 - 0.985)
        trades_98 = [t for t in parsed if 0.975 <= t["price"] <= 0.985]
        trades_99 = [t for t in parsed if 0.985 < t["price"] <= 0.995]
        
        # Check trades at ~0.01 (<= 0.015)
        trades_01 = [t for t in parsed if t["price"] <= 0.015]
        trades_02 = [t for t in parsed if 0.015 < t["price"] <= 0.025]

        # Total volume at 0.98
        vol_98 = sum(t["size"] for t in trades_98)
        vol_99 = sum(t["size"] for t in trades_99)
        vol_01 = sum(t["size"] for t in trades_01)
        vol_02 = sum(t["size"] for t in trades_02)

        # Did someone buy 0.98 early, and what happened after?
        first_98 = trades_98[0] if trades_98 else (trades_99[0] if trades_99 else None)
        
        timing_gap = None
        other_01_after_98 = 0
        reversed_after_98 = False

        if first_98:
            surged_token = first_98["outcome"]
            crushed_token = outcomes[1].upper() if surged_token == outcomes[0].upper() else outcomes[0].upper()

            # Did the token at 0.98 actually win?
            reversed_after_98 = (surged_token != winner)

            # Trades on crushed token AFTER first 0.98
            crushed_after = [t for t in parsed if t["ts"] >= first_98["ts"] and t["outcome"] == crushed_token]
            crushed_01 = [t for t in crushed_after if t["price"] <= 0.015]
            other_01_after_98 = sum(t["size"] for t in crushed_01)

            if crushed_01:
                timing_gap = round(crushed_01[0]["ts"] - first_98["ts"], 1)

        return {
            "coin": coin.upper(),
            "slug": slug,
            "window_time": datetime.datetime.utcfromtimestamp(w_s).strftime("%H:%M"),
            "winner": winner,
            "has_98": len(trades_98) > 0 or len(trades_99) > 0,
            "vol_98": vol_98,
            "vol_99": vol_99,
            "has_01": len(trades_01) > 0,
            "vol_01": vol_01,
            "vol_02": vol_02,
            "first_98_sec": first_98["sec"] if first_98 else None,
            "timing_gap": timing_gap,
            "other_01_after_98": other_01_after_98,
            "reversed_after_98": reversed_after_98,
            "total_trades": len(parsed)
        }
    except Exception as e:
        return None

tasks = []
for w in windows:
    tasks.append(("btc", w))
    tasks.append(("eth", w))

with ThreadPoolExecutor(max_workers=10) as ex:
    results = [r for r in ex.map(audit_candle, tasks) if r is not None]

results.sort(key=lambda x: (x["window_time"], x["coin"]))

print(f"\nSuccessfully collected trade data for {len(results)} markets over past 4 hours.\n")

# Summary aggregates
btc_results = [r for r in results if r["coin"] == "BTC"]
eth_results = [r for r in results if r["coin"] == "ETH"]

def print_coin_summary(name, list_res):
    print("=" * 80)
    print(f"📈 {name} PAST 4 HOURS ANALYSIS ({len(list_res)} candles checked)")
    print("=" * 80)
    with_98 = [r for r in list_res if r["has_98"]]
    with_01 = [r for r in list_res if r["has_01"]]
    both_in_same_candle = [r for r in list_res if r["has_98"] and r["has_01"]]
    
    total_98_shares = sum(r["vol_98"] for r in list_res)
    total_99_shares = sum(r["vol_99"] for r in list_res)
    total_01_shares = sum(r["vol_01"] for r in list_res)
    total_02_shares = sum(r["vol_02"] for r in list_res)

    print(f"Candles where price reached 0.98: {len(with_98)} / {len(list_res)} ({len(with_98)/max(1, len(list_res))*100:.1f}%)")
    print(f"Total Shares Available/Traded at $0.98: {total_98_shares:,.1f} sh (Avg per candle: {total_98_shares/max(1, len(with_98)):,.1f} sh)")
    print(f"Total Shares Available/Traded at $0.99: {total_99_shares:,.1f} sh")
    print(f"Candles where other side reached $0.01: {len(with_01)} / {len(list_res)} ({len(with_01)/max(1, len(list_res))*100:.1f}%)")
    print(f"Total Shares Available/Traded at $0.01: {total_01_shares:,.1f} sh (Avg per candle: {total_01_shares/max(1, len(with_01)):,.1f} sh)")
    print(f"Total Shares Available/Traded at $0.02: {total_02_shares:,.1f} sh")
    print(f"Candles having BOTH 0.98 AND 0.01 in the same candle: {len(both_in_same_candle)} / {len(list_res)}")

    reversals = [r for r in with_98 if r["reversed_after_98"]]
    print(f"⚠️ Reversals after hitting 0.98 (token at 0.98 LOST): {len(reversals)} / {len(with_98)}")

print_coin_summary("BTC", btc_results)
print_coin_summary("ETH", eth_results)

# Print detailed table of candles having 0.98
print("\n" + "=" * 105)
print(f"{'Time (UTC)':<10} | {'Coin':<5} | {'98 Shares':<12} | {'99 Shares':<12} | {'01 Shares':<12} | {'02 Shares':<12} | {'Time Gap':<10} | {'Reversed?'}")
print("-" * 105)

for r in results:
    if r["has_98"] or r["has_01"]:
        gap_str = f"{r['timing_gap']}s" if r["timing_gap"] is not None else "N/A"
        rev_str = "💥 YES (LOSS)" if r["reversed_after_98"] else "No (Won)"
        print(f"{r['window_time']:<10} | {r['coin']:<5} | {r['vol_98']:>10,.0f} sh | {r['vol_99']:>10,.0f} sh | {r['vol_01']:>10,.0f} sh | {r['vol_02']:>10,.0f} sh | {gap_str:<10} | {rev_str}")

print("=" * 105)
