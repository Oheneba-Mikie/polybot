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

# 24 hours = 288 five-minute candles
now = int(time.time())
cur_w = (now // 300) * 300
windows = [cur_w - (i * 300) for i in range(1, 289)] # 288 candles

start_ts = windows[-1] * 1000
end_ts   = (windows[0] + 300) * 1000

print("=" * 95)
print("🔍 24-HOUR EMPIRICAL AUDIT: ALL 5-MINUTE BITCOIN CANDLES WITH A $60+ WAVE")
print("=" * 95)
print(f"Time Window: {datetime.datetime.fromtimestamp(windows[-1], datetime.timezone.utc)} to {datetime.datetime.fromtimestamp(windows[0], datetime.timezone.utc)} UTC\n")

# Step 1: Fetch all 1m klines from Binance in bulk (300 candles = 2 calls)
print("Fetching 24 hours of 1-minute Bitcoin klines from Binance...")
b_data1 = requests.get(f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={start_ts}&limit=1000", timeout=10).json()
next_ts = b_data1[-1][0] + 60000
b_data2 = requests.get(f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={next_ts}&limit=1000", timeout=10).json()
all_klines = b_data1 + b_data2

# Build a dictionary of timestamp (sec) -> kline
# kline: [open_time, open, high, low, close, ...]
klines_dict = {int(k[0]//1000): {"open": float(k[1]), "high": float(k[2]), "low": float(k[3]), "close": float(k[4])} for k in all_klines}

print(f"Loaded {len(klines_dict)} 1-minute BTC bars.")

# Step 2: Identify every 5-minute window that had a move >= $60 from open
wave_60_windows = []

for w in windows:
    # 5 minutes: w, w+60, w+120, w+180, w+240
    m_bars = [klines_dict.get(w + i*60) for i in range(5) if (w + i*60) in klines_dict]
    if not m_bars:
        continue
    open_p = m_bars[0]["open"]
    high_p = max(b["high"] for b in m_bars)
    low_p  = min(b["low"] for b in m_bars)
    close_p = m_bars[-1]["close"]

    up_move   = high_p - open_p
    down_move = open_p - low_p
    max_move  = max(up_move, down_move)

    if max_move >= 60.0:
        wave_direction = "UP" if up_move >= down_move else "DOWN"
        wave_60_windows.append({
            "w_ts": w,
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "max_move": max_move,
            "wave_dir": wave_direction,
            "final_delta": close_p - open_p
        })

print(f"Found {len(wave_60_windows)} candles out of 288 ({len(wave_60_windows)/len(windows)*100:.1f}%) with a $60+ wave.\n")

# Step 3: Fetch Polymarket results for these $60+ wave candles
def audit_poly(wave_item):
    w_ts = wave_item["w_ts"]
    slug = f"btc-updown-5m-{w_ts}"
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

        p0, p1 = float(out_prices[0]), float(out_prices[1])
        winner = outcomes[0].upper() if p0 > p1 else outcomes[1].upper()

        # Fetch CLOB trades to check if 0.98 and 0.01 were traded
        trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=1000", timeout=4).json()
        
        hit_98 = False
        vol_98 = 0
        hit_01 = False
        vol_01 = 0

        if isinstance(trades, list):
            for t in trades:
                px = float(t.get("price", 0))
                sz = float(t.get("size", 0))
                if px >= 0.975:
                    hit_98 = True
                    vol_98 += sz
                elif px <= 0.015:
                    hit_01 = True
                    vol_01 += sz

        # Did the wave direction win?
        did_wave_win = (wave_item["wave_dir"] == winner)

        return {
            **wave_item,
            "time_str": datetime.datetime.fromtimestamp(w_ts, datetime.timezone.utc).strftime("%H:%M"),
            "winner": winner,
            "did_wave_win": did_wave_win,
            "hit_98": hit_98,
            "vol_98": vol_98,
            "hit_01": hit_01,
            "vol_01": vol_01
        }
    except Exception:
        return None

print(f"Auditing Polymarket trades and resolutions for all {len(wave_60_windows)} wave markets in parallel...")
with ThreadPoolExecutor(max_workers=12) as ex:
    poly_results = list(ex.map(audit_poly, wave_60_windows))

poly_results = [r for r in poly_results if r is not None]
poly_results.sort(key=lambda x: x["w_ts"])

# Step 4: Calculate aggregate statistics
total_waves = len(poly_results)
wins = sum(1 for r in poly_results if r["did_wave_win"])
losses = total_waves - wins
hit_98_count = sum(1 for r in poly_results if r["hit_98"])
hit_01_count = sum(1 for r in poly_results if r["hit_01"])
both_hit_count = sum(1 for r in poly_results if r["hit_98"] and r["hit_01"])

avg_98_vol = sum(r["vol_98"] for r in poly_results) / max(1, hit_98_count)
avg_01_vol = sum(r["vol_01"] for r in poly_results) / max(1, hit_01_count)

print("\n" + "=" * 95)
print(f"🏆 24-HOUR RESULTS FOR ALL $60+ WAVES ON BITCOIN:")
print("=" * 95)
print(f"1. Total $60+ Wave Opportunities: {total_waves} / 288 candles ({total_waves/288*100:.1f}% of all 5m windows)")
print(f"2. Win Rate (Did the $60+ Wave Win?): {wins} / {total_waves} ({wins/total_waves*100:.2f}%)")
print(f"3. Reversals (Lost after $60+ Wave): {losses} / {total_waves} ({losses/total_waves*100:.2f}%)")
print(f"4. Reached $0.98 on Polymarket: {hit_98_count} / {total_waves} ({hit_98_count/total_waves*100:.1f}%) | Avg Volume: {avg_98_vol:,.0f} shares")
print(f"5. Reached $0.01 on Polymarket: {hit_01_count} / {total_waves} ({hit_01_count/total_waves*100:.1f}%) | Avg Volume: {avg_01_vol:,.0f} shares")
print(f"6. BOTH $0.98 AND $0.01 available: {both_hit_count} / {total_waves} ({both_hit_count/total_waves*100:.1f}%)")
print("=" * 95)

# Step 5: Print detailed table of sample waves
print("\n📋 DETAILED LOG OF $60+ WAVE CANDLES (Sample of Recent Waves):")
print(f"{'Time (UTC)':<10} | {'Open Price':<12} | {'Max Wave':<11} | {'Wave Dir':<9} | {'Hit 98¢?':<10} | {'Hit 1¢?':<10} | {'Winner':<8} | {'Verdict'}")
print("-" * 95)

for r in poly_results[-35:]: # Show last 35 waves
    verdict = "✅ WON (100%)" if r["did_wave_win"] else "💥 REVERSED"
    hit_98_s = f"YES ({r['vol_98']:,.0f}sh)" if r["hit_98"] else "NO"
    hit_01_s = f"YES ({r['vol_01']:,.0f}sh)" if r["hit_01"] else "NO"
    print(f"{r['time_str']:<10} | ${r['open']:<11,.2f} | ${r['max_move']:<10.2f} | {r['wave_dir']:<9} | {hit_98_s:<10} | {hit_01_s:<10} | {r['winner']:<8} | {verdict}")

print("=" * 95)

# If any reversals occurred, print their forensics
reversals = [r for r in poly_results if not r["did_wave_win"]]
if reversals:
    print(f"\n⚠️ FORENSIC BREAKDOWN OF THE {len(reversals)} REVERSAL(S):")
    for rev in reversals:
        print(f"  • At {rev['time_str']} UTC: Open=${rev['open']:.2f}, Wave peaked at ${rev['max_move']:.2f} ({rev['wave_dir']}), but closed at ${rev['close']:.2f} (Final delta: {rev['final_delta']:+.2f}). Winner={rev['winner']}.")
else:
    print("\n🎉 ZERO REVERSALS! 100% of $60+ waves won.")
