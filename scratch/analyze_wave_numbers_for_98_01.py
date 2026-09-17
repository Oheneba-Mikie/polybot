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

# Check 50 recent 5-minute candles on BTC and ETH
now = int(time.time())
cur_w = (now // 300) * 300
windows = [cur_w - (i * 300) for i in range(1, 51)] # 50 candles = 4+ hours

print("=" * 90)
print("🔍 EMPIRICAL AUDIT: WHAT NUMBERS TRIGGER $0.98 AND $0.01 ON POLYMARKET?")
print("=" * 90)

# Fetch 1-second klines from Binance around each candle
def analyze_candle(item):
    coin, symbol, w_s = item
    slug = f"{coin}-updown-5m-{w_s}"
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
        if not r or not r[0].get("markets"):
            return None
        m = r[0]["markets"][0]
        cid = m.get("conditionId")
        outcomes = json.loads(m.get("outcomes") or "[]")
        out_prices = json.loads(m.get("outcomePrices") or "[]")
        if not cid or len(out_prices) < 2:
            return None

        # Fetch trades
        trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=1500", timeout=4).json()
        if not isinstance(trades, list) or len(trades) < 10:
            return None

        # Fetch 1-minute or 1-second candles from Binance for this 5m window
        b_url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&startTime={w_s * 1000}&endTime={(w_s + 300) * 1000}&limit=10"
        b_res = requests.get(b_url, timeout=4).json()
        if not isinstance(b_res, list) or not b_res:
            return None

        strike_open = float(b_res[0][1]) # open price at T=0

        parsed_trades = []
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
                parsed_trades.append({
                    "ts": tr_ts,
                    "sec": int(tr_ts - w_s),
                    "rem_sec": int(300 - (tr_ts - w_s)),
                    "price": float(t.get("price", 0)),
                    "size": float(t.get("size", 0)),
                    "outcome": str(t.get("outcome", "")).upper()
                })

        if not parsed_trades:
            return None

        parsed_trades.sort(key=lambda x: x["ts"])

        # Find first trade >= 0.975 (The 98c threshold)
        t_98 = [t for t in parsed_trades if t["price"] >= 0.975]
        # Find first trade <= 0.015 (The 1c threshold)
        t_01 = [t for t in parsed_trades if t["price"] <= 0.015]

        if not t_98:
            return None

        first_98 = t_98[0]
        
        # Estimate spot price at that second from the 1m Binance klines
        # Bin into 1m index
        min_idx = min(len(b_res) - 1, max(0, first_98["sec"] // 60))
        spot_at_98 = float(b_res[min_idx][4]) # close of that minute
        delta_at_98 = spot_at_98 - strike_open

        # If 0.01 was reached:
        sec_to_01 = None
        rem_sec_at_01 = None
        if t_01:
            first_01 = t_01[0]
            sec_to_01 = first_01["sec"]
            rem_sec_at_01 = first_01["rem_sec"]

        p0, p1 = float(out_prices[0]), float(out_prices[1])
        winner = outcomes[0].upper() if p0 > p1 else outcomes[1].upper()
        did_win = (first_98["outcome"] == winner)

        return {
            "coin": coin.upper(),
            "strike_open": strike_open,
            "sec_at_98": first_98["sec"],
            "rem_sec_at_98": first_98["rem_sec"],
            "delta_at_98": delta_at_98,
            "abs_delta": abs(delta_at_98),
            "spot_pct": (abs(delta_at_98) / strike_open) * 100,
            "outcome_98": first_98["outcome"],
            "did_win": did_win,
            "has_01": len(t_01) > 0,
            "rem_sec_at_01": rem_sec_at_01,
        }
    except Exception as e:
        return None

tasks = []
for w in windows:
    tasks.append(("btc", "BTCUSDT", w))
    tasks.append(("eth", "ETHUSDT", w))

with ThreadPoolExecutor(max_workers=10) as ex:
    results = [r for r in ex.map(analyze_candle, tasks) if r is not None]

btc_res = [r for r in results if r["coin"] == "BTC"]
eth_res = [r for r in results if r["coin"] == "ETH"]

print(f"Analyzed {len(results)} candles where 98c was reached ({len(btc_res)} BTC, {len(eth_res)} ETH).\n")

def summarize_coin(name, data, dollar_unit):
    print("=" * 80)
    print(f"📊 {name} WAVE NUMBERS TO TRIGGER $0.98 & $0.01:")
    print("=" * 80)
    if not data:
        print("No data")
        return

    deltas = [d["abs_delta"] for d in data]
    rems = [d["rem_sec_at_98"] for d in data]
    rems_01 = [d["rem_sec_at_01"] for d in data if d["rem_sec_at_01"] is not None]

    avg_delta = sum(deltas) / len(deltas)
    min_delta = min(deltas)
    max_delta = max(deltas)
    avg_rem = sum(rems) / len(rems)
    avg_rem_01 = sum(rems_01) / len(rems_01) if rems_01 else 0

    # Categorize by time remaining
    early_entries = [d for d in data if d["rem_sec_at_98"] > 120] # > 2 min left
    mid_entries   = [d for d in data if 60 <= d["rem_sec_at_98"] <= 120] # 1 to 2 min left
    late_entries  = [d for d in data if d["rem_sec_at_98"] < 60] # < 1 min left

    print(f"1. SPOT PRICE DISTANCE (How far price moved from open):")
    print(f"   • Average distance when 98¢ is hit: {dollar_unit}{avg_delta:,.2f} ({sum(d['spot_pct'] for d in data)/len(data):.3f}%)")
    print(f"   • Range: {dollar_unit}{min_delta:,.2f} to {dollar_unit}{max_delta:,.2f}")

    print(f"\n2. TIME REMAINING WHEN 98¢ IS HIT:")
    print(f"   • Average seconds remaining: {avg_rem:.1f}s left in candle (T+{300-avg_rem:.1f}s)")
    print(f"   • When 1¢ appears on losing side: typically with {avg_rem_01:.1f}s left")

    print(f"\n3. THE WAVE RELATIONSHIP (Time Remaining vs Required Move):")
    if early_entries:
        avg_early_d = sum(d["abs_delta"] for d in early_entries) / len(early_entries)
        print(f"   • Early Wave (> 2 min left): Requires {dollar_unit}{avg_early_d:,.1f}+ move to hit 98¢ (Needs a huge trend)")
    if mid_entries:
        avg_mid_d = sum(d["abs_delta"] for d in mid_entries) / len(mid_entries)
        print(f"   • Mid Wave (1 to 2 min left): Requires {dollar_unit}{avg_mid_d:,.1f} move to hit 98¢")
    if late_entries:
        avg_late_d = sum(d["abs_delta"] for d in late_entries) / len(late_entries)
        print(f"   • Late Wave (< 60 sec left): Requires only {dollar_unit}{avg_late_d:,.1f} move to hit 98¢")

summarize_coin("BITCOIN (BTC)", btc_res, "$")
summarize_coin("ETHEREUM (ETH)", eth_res, "$")

# Print 10 recent examples
print("\n" + "=" * 95)
print(f"{'Coin':<5} | {'Open Strike':<12} | {'Move Required':<15} | {'Move %':<10} | {'Sec Left @ 98c':<16} | {'Sec Left @ 1c':<14} | {'Won?'}")
print("-" * 95)
for d in results[:15]:
    rem_01_str = f"{d['rem_sec_at_01']}s" if d['rem_sec_at_01'] is not None else "Never"
    won_str = "✅ WON" if d['did_win'] else "❌ REVERSED"
    print(f"{d['coin']:<5} | ${d['strike_open']:<11,.2f} | ${d['abs_delta']:<14,.2f} | {d['spot_pct']:<9.3f}% | {d['rem_sec_at_98']:>3d}s left ({d['sec_at_98']:>3d}s in) | {rem_01_str:<14} | {won_str}")

print("=" * 95)
