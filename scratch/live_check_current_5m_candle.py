import requests
import json
import time
import datetime
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

print("="*95, flush=True)
print("🔴 LIVE 5-MINUTE BITCOIN MARKET CHECK (POLYMARKET REAL-TIME TAPES)", flush=True)
print("="*95, flush=True)

now_ts = int(time.time())
w_s = (now_ts // 300) * 300
w_prev = w_s - 300

# 1. Inspect Current Active Candle and Just-Completed Candle
for label, ts in [("JUST-COMPLETED CANDLE", w_prev), ("CURRENT LIVE ACTIVE CANDLE", w_s)]:
    slug = f"btc-updown-5m-{ts}"
    t_start = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%H:%M:%S UTC")
    t_end   = datetime.datetime.fromtimestamp(ts + 300, datetime.timezone.utc).strftime("%H:%M:%S UTC")
    
    print(f"\n📌 {label}: {slug} [{t_start} -> {t_end}]", flush=True)
    print("-" * 95, flush=True)
    
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
        if not r or not r[0].get("markets"):
            print("  [!] Market not found in Gamma API", flush=True)
            continue
            
        mkt = r[0]["markets"][0]
        cid = mkt.get("conditionId")
        tokens = json.loads(mkt.get("clobTokenIds", "[]"))
        outcomes = json.loads(mkt.get("outcomes", "[]"))
        
        up_token = tokens[0] if len(tokens) > 0 else None
        dn_token = tokens[1] if len(tokens) > 1 else None
        if len(outcomes) >= 2 and outcomes[0].lower() not in ("up", "yes"):
            up_token, dn_token = tokens[1], tokens[0]
            
        # Get Live CLOB Books if active
        if label == "CURRENT LIVE ACTIVE CANDLE" and up_token and dn_token:
            r_up_book = requests.get(f"{CLOB_HOST}/book?token_id={up_token}", timeout=3).json()
            r_dn_book = requests.get(f"{CLOB_HOST}/book?token_id={dn_token}", timeout=3).json()
            
            up_bids = r_up_book.get("bids", [])
            up_asks = r_up_book.get("asks", [])
            dn_bids = r_dn_book.get("bids", [])
            dn_asks = r_dn_book.get("asks", [])
            
            best_up_bid = float(up_bids[0]["price"]) if up_bids else None
            best_up_ask = float(up_asks[0]["price"]) if up_asks else None
            best_dn_bid = float(dn_bids[0]["price"]) if dn_bids else None
            best_dn_ask = float(dn_asks[0]["price"]) if dn_asks else None
            
            print(f"  ⚡ RIGHT NOW (Instantaneous Snapshot):", flush=True)
            print(f"     • UP Token:   Best Bid = ${best_up_bid} | Best Ask = ${best_up_ask}", flush=True)
            print(f"     • DOWN Token: Best Bid = ${best_dn_bid} | Best Ask = ${best_dn_ask}", flush=True)
            if best_up_ask and best_dn_ask:
                print(f"     • Instant Combined Ask Cost: ${best_up_ask + best_dn_ask:.3f} (Spend ${best_up_ask + best_dn_ask:.3f} to redeem $1.00)", flush=True)
                
        # Fetch Real Trade Tape for this candle
        r_tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=100", timeout=4).json()
        if not r_tr:
            print("  [!] No public trades recorded yet.", flush=True)
            continue
            
        candle_trades = []
        for t in r_tr:
            tr_ts = t.get("timestamp") or t.get("matchTime")
            if isinstance(tr_ts, str):
                try:
                    tr_ts = datetime.datetime.fromisoformat(tr_ts.replace("Z", "+00:00")).timestamp() if "T" in tr_ts else float(tr_ts)
                except: tr_ts = 0
            if tr_ts > 1e11: tr_ts /= 1000.0
            
            px = float(t.get("price", 0))
            side = str(t.get("side", "")).upper()
            outcome = str(t.get("outcome", "")).upper()
            sz = float(t.get("size", 0))
            
            if ts <= tr_ts <= ts + 300:
                t_str = datetime.datetime.fromtimestamp(tr_ts, datetime.timezone.utc).strftime("%H:%M:%S")
                candle_trades.append({"time": t_str, "ts": tr_ts, "side": side, "outcome": outcome, "px": px, "size": sz})
                
        print(f"\n  📊 ACTUAL TRADES EXECUTED ON ORDER BOOK ({len(candle_trades)} fills during this 5m window):", flush=True)
        if candle_trades:
            up_fills = [t for t in candle_trades if t["outcome"] in ("UP", "YES")]
            dn_fills = [t for t in candle_trades if t["outcome"] in ("DOWN", "NO")]
            
            min_up = min(t["px"] for t in up_fills) if up_fills else None
            max_up = max(t["px"] for t in up_fills) if up_fills else None
            min_dn = min(t["px"] for t in dn_fills) if dn_fills else None
            max_dn = max(t["px"] for t in dn_fills) if dn_fills else None
            
            print(f"     • UP Shares Traded:   Min = ${min_up} | Max = ${max_up} ({len(up_fills)} trades)", flush=True)
            print(f"     • DOWN Shares Traded: Min = ${min_dn} | Max = ${max_dn} ({len(dn_fills)} trades)", flush=True)
            
            if min_up and min_dn:
                combined_low = min_up + min_dn
                print(f"     • 🎯 COMBINED LOWEST ENTRY: ${min_up:.3f} (UP) + ${min_dn:.3f} (DOWN) = ${combined_low:.3f}", flush=True)
                if combined_low < 1.00:
                    profit = ((1.00 - combined_low) / combined_low) * 100.0
                    print(f"     • 💰 LOCKED PROFIT IF BOTH BOUGHT: +{profit:.1f}% (Spend ${combined_low:.2f} -> Redeem $1.00)", flush=True)
                else:
                    print(f"     • ⚠️ No sub-$1.00 wave occurred on this specific candle (Total = ${combined_low:.2f})", flush=True)
                    
            print(f"\n     Chronological Trade Log Sample:", flush=True)
            for t in candle_trades[:12]:
                print(f"       [{t['time']}] {t['side']} {t['size']} sh {t['outcome']} @ ${t['px']:.3f}", flush=True)
                
    except Exception as e:
        print(f"  [!] Error: {e}", flush=True)

print("\n" + "="*95, flush=True)
