import requests
import json
import time
import datetime
import sys
import statistics
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

print("="*110, flush=True)
print("🔍 24-HOUR POLYMARKET AUDIT: 5-MIN BTC MARKETS, 1.0 OUTCOMES & LIQUIDITY DRY-UP TIMING", flush=True)
print("="*110, flush=True)

now = time.time()
cur_w_s = int(now // 300) * 300
all_windows = [cur_w_s - (i * 300) for i in range(288)]

def process_window(w_s):
    slug = f"btc-updown-5m-{w_s}"
    t_start_utc = datetime.datetime.fromtimestamp(w_s, datetime.timezone.utc)
    candle_end_ts = w_s + 300
    
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4.0)
        if r.status_code != 200:
            return None
        data = r.json()
        if not data or not data[0].get("markets"):
            return None
            
        mkt = data[0]["markets"][0]
        cond_id = mkt.get("conditionId")
        outcome_prices_raw = mkt.get("outcomePrices") or "[]"
        prices = json.loads(outcome_prices_raw) if outcome_prices_raw else []
        
        up_final = float(prices[0]) if len(prices) > 0 else None
        dn_final = float(prices[1]) if len(prices) > 1 else None
        
        is_exact_1_0 = False
        if up_final is not None and dn_final is not None:
            if (up_final >= 0.999 and dn_final <= 0.001) or (dn_final >= 0.999 and up_final <= 0.001):
                is_exact_1_0 = True
                
        # Trades
        trades = []
        try:
            r_tr = requests.get(f"{DATA_HOST}/trades?market={cond_id}&limit=500", timeout=4.0)
            if r_tr.status_code == 200:
                trades = r_tr.json()
        except:
            pass
            
        up_trades = []
        dn_trades = []
        max_up_px = 0.0
        max_dn_px = 0.0
        min_up_px = 1.0
        min_dn_px = 1.0
        last_up_trade_time = None
        last_dn_trade_time = None
        last_trade_time = None
        
        for tr in trades:
            tr_ts = tr.get("timestamp") or tr.get("matchTime")
            if isinstance(tr_ts, str):
                try:
                    if "T" in tr_ts:
                        dt = datetime.datetime.fromisoformat(tr_ts.replace("Z", "+00:00"))
                        tr_ts = dt.timestamp()
                    else:
                        tr_ts = float(tr_ts)
                except:
                    tr_ts = None
            if tr_ts and tr_ts > 1e11:
                tr_ts = tr_ts / 1000.0
                
            px = float(tr.get("price", 0.0))
            outcome = tr.get("outcome", "").upper()
            
            if outcome in ("UP", "YES"):
                up_trades.append((tr_ts, px))
                max_up_px = max(max_up_px, px)
                min_up_px = min(min_up_px, px)
                if tr_ts and (last_up_trade_time is None or tr_ts > last_up_trade_time):
                    last_up_trade_time = tr_ts
            elif outcome in ("DOWN", "NO"):
                dn_trades.append((tr_ts, px))
                max_dn_px = max(max_dn_px, px)
                min_dn_px = min(min_dn_px, px)
                if tr_ts and (last_dn_trade_time is None or tr_ts > last_dn_trade_time):
                    last_dn_trade_time = tr_ts
                    
            if tr_ts and (last_trade_time is None or tr_ts > last_trade_time):
                last_trade_time = tr_ts
                
        sec_before_close_last_trade = (candle_end_ts - last_trade_time) if last_trade_time else None
        both_active_until_sec_before_close = None
        if last_up_trade_time and last_dn_trade_time:
            first_side_to_dryup_ts = min(last_up_trade_time, last_dn_trade_time)
            both_active_until_sec_before_close = candle_end_ts - first_side_to_dryup_ts
            
        return {
            "w_s": w_s,
            "slug": slug,
            "time_utc": t_start_utc.strftime("%H:%M"),
            "up_final": up_final,
            "dn_final": dn_final,
            "is_exact_1_0": is_exact_1_0,
            "trade_count": len(trades),
            "up_trade_count": len(up_trades),
            "dn_trade_count": len(dn_trades),
            "max_up_px": max_up_px,
            "max_dn_px": max_dn_px,
            "last_trade_before_close_s": sec_before_close_last_trade,
            "both_sides_active_until_before_close_s": both_active_until_sec_before_close,
        }
    except Exception as e:
        return None

print(f"Fetching 288 windows in parallel (25 threads)...", flush=True)
with ThreadPoolExecutor(max_workers=25) as executor:
    raw_results = list(executor.map(process_window, all_windows[::-1]))

results = [r for r in raw_results if r is not None]
unresolved_or_non_1 = [r for r in results if not r["is_exact_1_0"]]
contested_markets = [r for r in results if max(r["max_up_px"], r["max_dn_px"]) < 0.95 and r["trade_count"] > 5]
dryup_stats = [r["both_sides_active_until_before_close_s"] for r in results if r["both_sides_active_until_before_close_s"] is not None]

# Save output
with open("scratch/audit_24h_drying_results.json", "w", encoding="utf-8") as f:
    json.dump({"results": results, "unresolved": unresolved_or_non_1, "contested": contested_markets}, f, indent=2)

out_text = []
out_text.append("="*110)
out_text.append(f"📊 SUMMARY REPORT: 24-HOUR AUDIT OF {len(results)} 5-MINUTE BTC MARKETS")
out_text.append("="*110)

out_text.append(f"\n1. 🎯 FINAL RESOLUTION (1.0 vs Non-1.0):")
out_text.append(f"   • Total Processed 5m Markets: {len(results)}")
exact_1_count = len(results) - len(unresolved_or_non_1)
out_text.append(f"   • Markets Resolved to Exact 1.0 / 0.0: {exact_1_count} ({exact_1_count/max(1, len(results))*100:.1f}%)")
out_text.append(f"   • Markets that DID NOT reach 1.0 resolution (or ongoing / ties): {len(unresolved_or_non_1)}")

if unresolved_or_non_1:
    out_text.append(f"\n   Detailed List of Non-1.0 / Ongoing Resolutions:")
    for m in unresolved_or_non_1:
        out_text.append(f"     - {m['slug']} ({m['time_utc']} UTC): UP={m['up_final']} | DOWN={m['dn_final']} | Trades={m['trade_count']}")

out_text.append(f"\n2. ⚡ IN-PLAY CONTESTED MARKETS (Where traded price stayed < $0.95 until the close):")
out_text.append(f"   • Total Contested Markets: {len(contested_markets)}")
for c in contested_markets[:15]:
    out_text.append(f"     - {c['slug']} ({c['time_utc']} UTC): Max UP = ${c['max_up_px']:.2f} | Max DOWN = ${c['max_dn_px']:.2f} | Trades = {c['trade_count']}")

out_text.append(f"\n3. ⏱️ HOW LONG IT TOOK FOR BOTH ENDS TO DRY UP (When the first leg stopped trading):")
if dryup_stats:
    avg_dry = statistics.mean(dryup_stats)
    med_dry = statistics.median(dryup_stats)
    min_dry = min(dryup_stats)
    max_dry = max(dryup_stats)
    
    within_30s = sum(1 for d in dryup_stats if d <= 30)
    within_60s = sum(1 for d in dryup_stats if 30 < d <= 60)
    within_120s = sum(1 for d in dryup_stats if 60 < d <= 120)
    over_120s = sum(1 for d in dryup_stats if d > 120)
    
    out_text.append(f"   • Both sides (UP & DOWN) actively traded until an average of: T-{avg_dry:.1f}s before candle close")
    out_text.append(f"   • Median dry-up time: T-{med_dry:.1f}s before candle close")
    out_text.append(f"   • Range: T-{min_dry:.1f}s to T-{max_dry:.1f}s")
    out_text.append(f"\n   📈 Dry-Up Timing Breakdown (When the first leg stopped trading):")
    out_text.append(f"     • Both ends active until final 30s (T-30s to T-0s):  {within_30s} markets ({within_30s/len(dryup_stats)*100:.1f}%)")
    out_text.append(f"     • Both ends active until T-60s to T-30s:              {within_60s} markets ({within_60s/len(dryup_stats)*100:.1f}%)")
    out_text.append(f"     • Both ends active until T-120s to T-60s:             {within_120s} markets ({within_120s/len(dryup_stats)*100:.1f}%)")
    out_text.append(f"     • One end dried up early (>120s before close):        {over_120s} markets ({over_120s/len(dryup_stats)*100:.1f}%)")

out_text.append("\n" + "="*110)

full_report = "\n".join(out_text)
print(full_report, flush=True)
with open("scratch/24h_dryup_summary.txt", "w", encoding="utf-8") as f:
    f.write(full_report)
