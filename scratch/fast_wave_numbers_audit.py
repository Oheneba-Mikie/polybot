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

# Check past 40 candles (3+ hours)
now = int(time.time())
cur_w = (now // 300) * 300
windows = [cur_w - (i * 300) for i in range(1, 41)]

start_ts = windows[-1] * 1000
end_ts   = (windows[0] + 300) * 1000

print("=" * 90)
print("🔍 EXACT WAVE NUMBERS TO TRIGGER $0.98 & $0.01 (BTC & ETH)")
print("=" * 90)
print(f"Fetching Binance 1m klines for BTC and ETH in bulk...")

# 1 bulk call for BTC, 1 bulk call for ETH
btc_klines = requests.get(f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={start_ts}&endTime={end_ts}&limit=500", timeout=10).json()
eth_klines = requests.get(f"https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1m&startTime={start_ts}&endTime={end_ts}&limit=500", timeout=10).json()

# Map timestamp (sec) -> 1m close price
btc_price_map = {int(k[0]//1000): float(k[4]) for k in btc_klines}
eth_price_map = {int(k[0]//1000): float(k[4]) for k in eth_klines}
# Map timestamp (sec) -> 1m open price
btc_open_map = {int(k[0]//1000): float(k[1]) for k in btc_klines}
eth_open_map = {int(k[0]//1000): float(k[1]) for k in eth_klines}

print(f"Loaded {len(btc_price_map)} BTC 1m points, {len(eth_price_map)} ETH 1m points.")

def process_market(item):
    coin, w_s = item
    price_map = btc_price_map if coin == "BTC" else eth_price_map
    open_map  = btc_open_map if coin == "BTC" else eth_open_map
    
    strike_open = open_map.get(w_s)
    if not strike_open:
        # fallback to nearest
        keys = sorted(open_map.keys())
        nearest = min(keys, key=lambda k: abs(k - w_s))
        strike_open = open_map[nearest]

    slug = f"{coin.lower()}-updown-5m-{w_s}"
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
        if not r or not r[0].get("markets"):
            return None
        m = r[0]["markets"][0]
        cid = m.get("conditionId")
        outcomes = json.loads(m.get("outcomes") or "[]")
        out_prices = json.loads(m.get("outcomePrices") or "[]")
        if not cid or len(out_prices) < 2:
            return None

        trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=1500", timeout=3).json()
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

            if w_s <= tr_ts <= w_s + 300:
                parsed.append({
                    "ts": tr_ts,
                    "sec": int(tr_ts - w_s),
                    "rem_sec": int(300 - (tr_ts - w_s)),
                    "price": float(t.get("price", 0)),
                    "size": float(t.get("size", 0)),
                    "outcome": str(t.get("outcome", "")).upper()
                })

        if not parsed:
            return None

        parsed.sort(key=lambda x: x["ts"])

        t_98 = [t for t in parsed if t["price"] >= 0.975]
        t_01 = [t for t in parsed if t["price"] <= 0.015]

        if not t_98:
            return None

        first_98 = t_98[0]
        # Spot price at that minute
        min_sec = (first_98["sec"] // 60) * 60 + w_s
        spot_at_98 = price_map.get(min_sec, strike_open)
        delta_at_98 = spot_at_98 - strike_open

        first_01_rem = t_01[0]["rem_sec"] if t_01 else None

        p0, p1 = float(out_prices[0]), float(out_prices[1])
        winner = outcomes[0].upper() if p0 > p1 else outcomes[1].upper()
        did_win = (first_98["outcome"] == winner)

        return {
            "coin": coin,
            "strike_open": strike_open,
            "sec_in": first_98["sec"],
            "sec_rem": first_98["rem_sec"],
            "spot_move": abs(delta_at_98),
            "spot_pct": (abs(delta_at_98) / strike_open) * 100,
            "has_01": len(t_01) > 0,
            "sec_rem_01": first_01_rem,
            "did_win": did_win
        }
    except Exception:
        return None

tasks = []
for w in windows:
    tasks.append(("BTC", w))
    tasks.append(("ETH", w))

with ThreadPoolExecutor(max_workers=12) as ex:
    results = [r for r in ex.map(process_market, tasks) if r is not None]

btc_res = [r for r in results if r["coin"] == "BTC"]
eth_res = [r for r in results if r["coin"] == "ETH"]

print(f"Analyzed {len(results)} valid markets ({len(btc_res)} BTC, {len(eth_res)} ETH).\n")

def print_breakdown(coin_name, res, unit):
    print("=" * 80)
    print(f"🎯 {coin_name}: EXACT WAVE NUMBERS REQUIRED FOR $0.98 & $0.01")
    print("=" * 80)
    if not res:
        print("No data")
        return

    moves = [r["spot_move"] for r in res]
    pcts  = [r["spot_pct"] for r in res]
    rems  = [r["sec_rem"] for r in res]

    print(f"1. OVERALL REQUIRED MOVE TO HIT $0.98:")
    print(f"   • Average Spot Move: {unit}{sum(moves)/len(moves):,.2f} ({sum(pcts)/len(pcts):.3f}%)")
    print(f"   • Minimum Spot Move Ever Observed: {unit}{min(moves):,.2f}")
    print(f"   • Maximum Spot Move Observed: {unit}{max(moves):,.2f}")

    print(f"\n2. THE TIME-DEPENDENT WAVE MATRIX (How much move is needed at what time):")
    # Early: > 180s left (first 2 minutes)
    early = [r for r in res if r["sec_rem"] >= 180]
    # Mid: 60s to 180s left (minutes 2 to 4)
    mid = [r for r in res if 60 <= r["sec_rem"] < 180]
    # Late: < 60s left (final minute)
    late = [r for r in res if r["sec_rem"] < 60]

    if early:
        avg_e = sum(r["spot_move"] for r in early) / len(early)
        print(f"   • EARLY WAVE (> 3m left / T-180s+):  Needs {unit}{avg_e:,.2f} ({sum(r['spot_pct'] for r in early)/len(early):.2f}%) move")
    else:
        print(f"   • EARLY WAVE (> 3m left): Almost never hits 98¢ early unless there is a giant black-swan spike")

    if mid:
        avg_m = sum(r["spot_move"] for r in mid) / len(mid)
        print(f"   • MID WAVE (1m to 3m left):          Needs {unit}{avg_m:,.2f} ({sum(r['spot_pct'] for r in mid)/len(mid):.2f}%) move")

    if late:
        avg_l = sum(r["spot_move"] for r in late) / len(late)
        print(f"   • LATE WAVE (Final 60 seconds):      Needs only {unit}{avg_l:,.2f} ({sum(r['spot_pct'] for r in late)/len(late):.2f}%) move")

    print(f"\n3. WHEN DOES $0.01 APPEAR ON THE LOSING SIDE?")
    with_01 = [r for r in res if r["has_01"]]
    print(f"   • 1¢ appears in {len(with_01)} / {len(res)} markets ({len(with_01)/len(res)*100:.1f}%)")
    if with_01:
        avg_rem_01 = sum(r["sec_rem_01"] for r in with_01) / len(with_01)
        print(f"   • 1¢ appears on average with {avg_rem_01:.1f} seconds remaining in the candle (T+{300-avg_rem_01:.1f}s)")

print_breakdown("BITCOIN (BTC)", btc_res, "$")
print_breakdown("ETHEREUM (ETH)", eth_res, "$")

print("\n" + "=" * 90)
print("📋 10 REAL CHRONOLOGICAL EXAMPLES (Price Move -> 98c Trigger -> 1c Trigger):")
print(f"{'Coin':<5} | {'Open Strike':<12} | {'Move to hit 98c':<18} | {'Time of 98c':<16} | {'Time of 1c':<14} | {'Result'}")
print("-" * 90)
for r in results[:10]:
    t_01_str = f"T+{300-r['sec_rem_01']}s" if r['has_01'] else "Never"
    print(f"{r['coin']:<5} | ${r['strike_open']:<11,.2f} | ${r['spot_move']:<7,.2f} ({r['spot_pct']:.3f}%) | T+{r['sec_in']:>3d}s (T-{r['sec_rem']:>2d}s)  | {t_01_str:<14} | {'Won' if r['did_win'] else 'Reversed'}")
print("=" * 90)
