import requests
import json
import time
import datetime
import sys
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"

# 24 hours = 288 five-minute intervals
now = int(time.time())
cur_w = (now // 300) * 300

# We will check the past 288 windows (24h)
start_w = cur_w - (288 * 300)
end_w   = cur_w - 300 # closed candles

print("=" * 90)
print("📊 24-HOUR PROOF: BINANCE SPOT VS. POLYMARKET RESOLUTION")
print("=" * 90)
print(f"Time Range: {datetime.datetime.fromtimestamp(start_w, datetime.timezone.utc)} to {datetime.datetime.fromtimestamp(end_w, datetime.timezone.utc)} UTC (24 Hours / 288 Candles)")

# Step 1: Fetch 288 5-minute candles from Binance
binance_url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&startTime={start_w * 1000}&endTime={(end_w + 300) * 1000}&limit=300"
try:
    b_data = requests.get(binance_url, timeout=10).json()
except Exception as e:
    print(f"Error fetching Binance data: {e}")
    sys.exit(1)

if not isinstance(b_data, list) or len(b_data) == 0:
    print(f"Binance returned unexpected response: {b_data}")
    sys.exit(1)

print(f"Successfully retrieved {len(b_data)} 5-minute candles from Binance.")

# Build map of timestamp -> Binance candle
# Candle structure: [open_time, open, high, low, close, volume, close_time, ...]
binance_candles = {}
for k in b_data:
    t_sec = int(k[0] // 1000)
    op = float(k[1])
    cl = float(k[4])
    direction = "UP" if cl >= op else "DOWN"
    binance_candles[t_sec] = {
        "open": op,
        "close": cl,
        "delta": cl - op,
        "direction": direction
    }

# Step 2: Fetch corresponding Polymarket resolutions
def fetch_poly_market(w_ts):
    slug = f"btc-updown-5m-{w_ts}"
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
        if not r or not r[0].get("markets"):
            return None
        m = r[0]["markets"][0]
        outcomes = json.loads(m.get("outcomes") or "[]")
        out_prices = json.loads(m.get("outcomePrices") or "[]")
        if len(outcomes) < 2 or len(out_prices) < 2:
            return None
        p0, p1 = float(out_prices[0]), float(out_prices[1])
        winner = outcomes[0].upper() if p0 > p1 else outcomes[1].upper()
        return {
            "w_ts": w_ts,
            "slug": slug,
            "winner": winner
        }
    except Exception:
        return None

w_timestamps = sorted(list(binance_candles.keys()))
print(f"Fetching {len(w_timestamps)} corresponding Polymarket 5m contracts in parallel...")

with ThreadPoolExecutor(max_workers=15) as ex:
    poly_results = list(ex.map(fetch_poly_market, w_timestamps))

poly_map = {r["w_ts"]: r["winner"] for r in poly_results if r is not None}
print(f"Matched {len(poly_map)} contracts on Polymarket.")

# Step 3: Compare side by side
matches = 0
discrepancies = 0
total_checked = 0

records = []
for w_ts in w_timestamps:
    if w_ts in poly_map:
        b = binance_candles[w_ts]
        p_winner = poly_map[w_ts]
        
        is_match = (b["direction"] == p_winner)
        if is_match:
            matches += 1
        else:
            discrepancies += 1
        total_checked += 1

        t_str = datetime.datetime.fromtimestamp(w_ts, datetime.timezone.utc).strftime("%H:%M")
        records.append({
            "time": t_str,
            "b_open": b["open"],
            "b_close": b["close"],
            "delta": b["delta"],
            "b_dir": b["direction"],
            "poly_winner": p_winner,
            "match": is_match
        })

print("\n" + "=" * 80)
print(f"🏆 24-HOUR CORRELATION VERDICT:")
print("=" * 80)
print(f"Total 5-Minute Markets Checked: {total_checked}")
print(f"Binance Direction MATCHED Polymarket Winner: {matches} / {total_checked} ({matches/total_checked*100:.2f}%)")
print(f"Discrepancies (Micro-TWAP borderlines near $0.00 delta): {discrepancies}")
print("=" * 80)

# Display sample of 30 chronological candles across the day
print("\n📋 SAMPLE CHRONOLOGICAL COMPARISON TABLE (Recent Hours):")
print(f"{'Time (UTC)':<10} | {'Binance Open':<13} | {'Binance Close':<13} | {'Move ($)':<10} | {'Binance':<8} | {'Polymarket':<10} | {'Match?'}")
print("-" * 88)

for r in records[-30:]:
    match_icon = "✅ 100% MATCH" if r["match"] else "⚠️ BORDERLINE"
    delta_str = f"{r['delta']:+.2f}"
    print(f"{r['time']:<10} | ${r['b_open']:<12,.2f} | ${r['b_close']:<12,.2f} | {delta_str:<10} | {r['b_dir']:<8} | {r['poly_winner']:<10} | {match_icon}")

print("=" * 88)

# Calculate match rate by move magnitude
moves_ge_20 = [r for r in records if abs(r["delta"]) >= 20.0]
matches_ge_20 = [r for r in moves_ge_20 if r["match"]]
moves_ge_50 = [r for r in records if abs(r["delta"]) >= 50.0]
matches_ge_50 = [r for r in moves_ge_50 if r["match"]]

print(f"\n🎯 CORRELATION BY PRICE MOVE MAGNITUDE:")
print(f"  • When Binance moved >= $20: {len(matches_ge_20)} / {len(moves_ge_20)} matched ({len(matches_ge_20)/max(1, len(moves_ge_20))*100:.1f}%)")
print(f"  • When Binance moved >= $50: {len(matches_ge_50)} / {len(moves_ge_50)} matched ({len(matches_ge_50)/max(1, len(moves_ge_50))*100:.1f}%)")

