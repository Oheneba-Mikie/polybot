import os
import sys
import time
import json
import datetime
import requests
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

headers = {"User-Agent": "Mozilla/5.0"}

def audit_single_candle(asset_prefix, w_s):
    slug = f"{asset_prefix}-updown-5m-{w_s}"
    w_e = w_s + 300
    utc_str = datetime.datetime.fromtimestamp(w_s, tz=datetime.timezone.utc).strftime("%H:%M:%S UTC")
    
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", headers=headers, timeout=5).json()
        if not r or not r[0].get("markets"):
            return None
        
        m = r[0]["markets"][0]
        title = m.get("question") or m.get("description") or slug
        clob_tokens = json.loads(m.get("clobTokenIds", "[]")) if isinstance(m.get("clobTokenIds"), str) else m.get("clobTokenIds", [])
        outcome_prices = json.loads(m.get("outcomePrices", "[]")) if isinstance(m.get("outcomePrices"), str) else m.get("outcomePrices", [])
        
        if len(clob_tokens) < 2:
            return None
        
        up_token, dn_token = clob_tokens[0], clob_tokens[1]
        
        # Fetch trades for up and dn tokens
        r_up = requests.get(f"{DATA_HOST}/trades?asset_id={up_token}&limit=200", headers=headers, timeout=5).json()
        r_dn = requests.get(f"{DATA_HOST}/trades?asset_id={dn_token}&limit=200", headers=headers, timeout=5).json()
        
        up_trades = r_up if isinstance(r_up, list) else []
        dn_trades = r_dn if isinstance(r_dn, list) else []
        
        # Filter trades within the window [w_s, w_e]
        up_w = [t for t in up_trades if w_s <= int(t.get("timestamp", 0)) <= w_e]
        dn_w = [t for t in dn_trades if w_s <= int(t.get("timestamp", 0)) <= w_e]
        
        # Look for cross opportunities / min prices
        min_up_p = min([float(t["price"]) for t in up_w]) if up_w else 1.0
        min_dn_p = min([float(t["price"]) for t in dn_w]) if dn_w else 1.0
        
        max_up_size = max([float(t.get("size", 0)) for t in up_w]) if up_w else 0.0
        max_dn_size = max([float(t.get("size", 0)) for t in dn_w]) if dn_w else 0.0
        
        # Check concurrent trades within 10 seconds of each other
        cross_events = []
        for u in up_w:
            u_t = int(u.get("timestamp", 0))
            u_p = float(u["price"])
            u_s = float(u.get("size", 0))
            for d in dn_w:
                d_t = int(d.get("timestamp", 0))
                d_p = float(d["price"])
                d_s = float(d.get("size", 0))
                
                if abs(u_t - d_t) <= 15: # within 15 seconds
                    comb = round(u_p + d_p, 3)
                    if comb < 1.000:
                        cross_events.append({
                            "time_diff": abs(u_t - d_t),
                            "up_p": u_p,
                            "up_s": u_s,
                            "dn_p": d_p,
                            "dn_s": d_s,
                            "comb": comb,
                            "min_size": min(u_s, d_s)
                        })
                        
        return {
            "asset": asset_prefix.upper(),
            "slug": slug,
            "window_start": w_s,
            "utc": utc_str,
            "title": title,
            "up_token": up_token,
            "dn_token": dn_token,
            "up_trades_count": len(up_w),
            "dn_trades_count": len(dn_w),
            "min_up_p": min_up_p,
            "min_dn_p": min_dn_p,
            "min_combined": round(min_up_p + min_dn_p, 3),
            "max_up_size": max_up_size,
            "max_dn_size": max_dn_size,
            "cross_events": cross_events,
            "has_100_cross": any(c["min_size"] >= 100 for c in cross_events),
            "has_50_cross": any(c["min_size"] >= 50 for c in cross_events),
        }
    except Exception as e:
        return None

def check_live_books(asset_prefix):
    now = int(time.time())
    cur_w = (now // 300) * 300
    slug = f"{asset_prefix}-updown-5m-{cur_w}"
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", headers=headers, timeout=4).json()
        if not r or not r[0].get("markets"):
            return None
        m = r[0]["markets"][0]
        tokens = json.loads(m.get("clobTokenIds", "[]"))
        if len(tokens) < 2:
            return None
        
        r_up = requests.get(f"{CLOB_HOST}/book?token_id={tokens[0]}", headers=headers, timeout=4).json()
        r_dn = requests.get(f"{CLOB_HOST}/book?token_id={tokens[1]}", headers=headers, timeout=4).json()
        
        asks_up = sorted(r_up.get("asks", []), key=lambda x: float(x["price"]))
        asks_dn = sorted(r_dn.get("asks", []), key=lambda x: float(x["price"]))
        
        up_p = float(asks_up[0]["price"]) if asks_up else 1.0
        up_s = float(asks_up[0]["size"]) if asks_up else 0.0
        dn_p = float(asks_dn[0]["price"]) if asks_dn else 1.0
        dn_s = float(asks_dn[0]["size"]) if asks_dn else 0.0
        
        return {
            "asset": asset_prefix.upper(),
            "slug": slug,
            "up_p": up_p,
            "up_s": up_s,
            "dn_p": dn_p,
            "dn_s": dn_s,
            "comb": round(up_p + dn_p, 3),
            "depth_50": (up_s >= 50 and dn_s >= 50),
            "depth_100": (up_s >= 100 and dn_s >= 100)
        }
    except Exception:
        return None

def run_full_audit():
    now = int(time.time())
    current_w = (now // 300) * 300
    # 2 hours = 24 windows of 5m
    past_windows = [current_w - i * 300 for i in range(1, 25)]
    
    print("=" * 80)
    print(f"📊 2-HOUR AUDIT: ETH 5M & SOLANA 5M ARBITRAGE OPPORTUNITY ANALYSIS")
    print(f"Time Range: {datetime.datetime.fromtimestamp(past_windows[-1], tz=datetime.timezone.utc).strftime('%H:%M:%S')} UTC to {datetime.datetime.fromtimestamp(current_w, tz=datetime.timezone.utc).strftime('%H:%M:%S')} UTC (24 candles each)")
    print("=" * 80)
    
    with ThreadPoolExecutor(max_workers=10) as ex:
        eth_results = list(filter(None, ex.map(lambda w: audit_single_candle("eth", w), past_windows)))
        sol_results = list(filter(None, ex.map(lambda w: audit_single_candle("sol", w), past_windows)))
    
    for name, res in [("ETHEREUM 5M (ETH)", eth_results), ("SOLANA 5M (SOL)", sol_results)]:
        print(f"\n==================== {name} (PAST 2 HOURS) ====================")
        print(f"Total Evaluated Candles: {len(res)}")
        
        total_arb_windows = [r for r in res if r["min_combined"] < 1.000]
        arb_50_windows = [r for r in res if r["has_50_cross"] or (r["min_combined"] < 1.000 and r["max_up_size"] >= 50 and r["max_dn_size"] >= 50)]
        arb_100_windows = [r for r in res if r["has_100_cross"] or (r["min_combined"] < 1.000 and r["max_up_size"] >= 100 and r["max_dn_size"] >= 100)]
        
        print(f"Candles with Sub-$1.00 Combined Price: {len(total_arb_windows)} / {len(res)} ({len(total_arb_windows)/max(1,len(res))*100:.1f}%)")
        print(f"Candles with 50+ Shares on BOTH Sides:  {len(arb_50_windows)} / {len(res)} ({len(arb_50_windows)/max(1,len(res))*100:.1f}%)")
        print(f"Candles with 100+ Shares on BOTH Sides: {len(arb_100_windows)} / {len(res)} ({len(arb_100_windows)/max(1,len(res))*100:.1f}%)")
        
        print("\nCandle Breakdown:")
        for r in sorted(res, key=lambda x: x["window_start"]):
            status_tag = "❌ NO ARB"
            if r["min_combined"] < 1.000:
                if r["has_100_cross"] or (r["max_up_size"] >= 100 and r["max_dn_size"] >= 100):
                    status_tag = "🚀 ARB 100+ SH"
                elif r["has_50_cross"] or (r["max_up_size"] >= 50 and r["max_dn_size"] >= 50):
                    status_tag = "⚡ ARB 50+ SH"
                else:
                    status_tag = "⚠️ ARB <50 SH"
            
            print(f"  [{r['utc']}] {r['slug']} | Min Comb: ${r['min_combined']:.3f} (UP min ${r['min_up_p']:.2f}, DN min ${r['min_dn_p']:.2f}) | Max Size: UP={r['max_up_size']:.0f}sh, DN={r['max_dn_size']:.0f}sh | {status_tag}")
    
    print("\n" + "=" * 80)
    print("🔴 LIVE ORDER BOOK SNAPSHOT RIGHT NOW (CURRENT LIVE CANDLE)")
    print("=" * 80)
    for asset in ["btc", "eth", "sol"]:
        live = check_live_books(asset)
        if live:
            print(f"{live['asset']} 5M LIVE: UP ${live['up_p']:.2f} ({live['up_s']:.1f} sh) | DN ${live['dn_p']:.2f} ({live['dn_s']:.1f} sh) | Comb: ${live['comb']:.3f} | 50+ Depth: {live['depth_50']} | 100+ Depth: {live['depth_100']}")
        else:
            print(f"{asset.upper()} 5M LIVE: Unable to fetch active candle order book")

if __name__ == "__main__":
    run_full_audit()
