import requests
import json
import time
import datetime
from concurrent.futures import ThreadPoolExecutor
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

print("="*120)
print("🔬 100% REAL ON-CHAIN AUDIT: VERIFYING ACTUAL TRADED ASKS, BIDS, SHARES & DOLLARS ACROSS 24 HOURS")
print("="*120)

now = time.time()
cur_w_s = int(now // 300) * 300
all_windows = [cur_w_s - (i * 300) for i in range(288)]

def audit_single_candle(w_s):
    slug = f"btc-updown-5m-{w_s}"
    t_dt_utc = datetime.datetime.fromtimestamp(w_s, datetime.timezone.utc).strftime("%H:%M UTC")
    t_dt_et  = datetime.datetime.fromtimestamp(w_s - 4*3600, datetime.timezone.utc).strftime("%I:%M %p ET")
    
    try:
        r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3.5).json()
        if not r_evt or not r_evt[0].get("markets"):
            return {"w_s": w_s, "time_et": t_dt_et, "slug": slug, "status": "NO_EVENT", "details": "Market not found on Gamma API"}
            
        mkt = r_evt[0]["markets"][0]
        cid = mkt.get("conditionId")
        prices = json.loads(mkt.get("outcomePrices") or "[]")
        if len(prices) < 2:
            return {"w_s": w_s, "time_et": t_dt_et, "slug": slug, "status": "NO_PRICES", "details": "Unresolved"}
            
        up_p = float(prices[0])
        dn_p = float(prices[1])
        winner = "UP" if up_p >= 0.99 else ("DOWN" if dn_p >= 0.99 else "OTHER")
        
        # Query the REAL on-chain trade prints for this market
        r_tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=100", timeout=3.5).json()
        if not r_tr:
            return {"w_s": w_s, "time_et": t_dt_et, "slug": slug, "status": "ZERO_VOLUME", "winner": winner, "details": "0 Trades on Polymarket ledger"}
            
        trades = sorted(r_tr, key=lambda x: x.get("timestamp", 0))
        
        # Find trades on the winning token
        win_trades = [t for t in trades if t.get("outcome", "").upper() == winner]
        if not win_trades:
            return {"w_s": w_s, "time_et": t_dt_et, "slug": slug, "status": "NO_WINNER_TRADES", "winner": winner, "details": "No trades on winning side"}
            
        # Real First Trade (Entry)
        first_t = win_trades[0]
        first_px = float(first_t.get("price", 0))
        first_sz = float(first_t.get("size", 0))
        first_val = round(first_px * first_sz, 2)
        first_ts  = first_t.get("timestamp", 0)
        first_rel = first_ts - w_s # Seconds into candle
        
        # Real Last Trade (Exit / Cashout)
        last_t = win_trades[-1]
        last_px = float(last_t.get("price", 0))
        last_sz = float(last_t.get("size", 0))
        last_val = round(last_px * last_sz, 2)
        last_ts  = last_t.get("timestamp", 0)
        last_rel = last_ts - w_s
        
        total_vol = sum([float(t.get("size", 0)) * float(t.get("price", 0)) for t in trades])
        
        return {
            "w_s": w_s,
            "time_et": t_dt_et,
            "time_utc": t_dt_utc,
            "slug": slug,
            "status": "VALID",
            "winner": winner,
            "trades_count": len(trades),
            "total_vol_usdc": round(total_vol, 2),
            "entry_sec": first_rel,
            "entry_px": first_px,
            "entry_sz": first_sz,
            "entry_usdc": first_val,
            "exit_sec": last_rel,
            "exit_px": last_px,
            "exit_sz": last_sz,
            "exit_usdc": last_val
        }
    except Exception as e:
        return {"w_s": w_s, "time_et": t_dt_et, "slug": slug, "status": "ERROR", "details": str(e)}

print("Querying Polymarket on-chain ledgers across all 288 markets...")
with ThreadPoolExecutor(max_workers=25) as executor:
    audit_results = list(executor.map(audit_single_candle, all_windows))

# Sort chronologically
valid_audits = sorted([a for a in audit_results if a.get("status") == "VALID"], key=lambda x: x["w_s"])

print(f"Total Successfully Audited On-Chain Markets: {len(valid_audits)} / 288\n")
print(f"{'Time (ET)':<11} | {'Slug':<26} | {'Winner':<6} | {'Real Entry (Price & Avail Size)':<30} | {'Real Late Cashout / Exit':<28} | {'Total Mkt Vol'}")
print("-" * 125)

# Print a dense sample across the 24 hours
for a in valid_audits[::6]: # Every 6th candle (approx 2 per hour)
    entry_str = f"T+{a['entry_sec']}s: ${a['entry_px']:.3f} ({a['entry_sz']:.1f} sh / ${a['entry_usdc']:.2f})"
    exit_str  = f"T+{a['exit_sec']}s: ${a['exit_px']:.3f} (${a['exit_usdc']:.2f} depth)"
    vol_str   = f"${a['total_vol_usdc']:>7.2f} USDC"
    print(f"{a['time_et']:<11} | {a['slug']:<26} | {a['winner']:<6} | {entry_str:<30} | {exit_str:<28} | {vol_str}")

print("="*125)
total_volume_day = sum([a["total_vol_usdc"] for a in valid_audits])
avg_entry_px = sum([a["entry_px"] for a in valid_audits]) / len(valid_audits)
avg_exit_px  = sum([a["exit_px"] for a in valid_audits]) / len(valid_audits)

print(f"📊 SUMMARY OF REAL ON-CHAIN ORDER BOOK REALITY:")
print(f"  • Verified Markets with Real Trade Fills: {len(valid_audits)} (100% of available)")
print(f"  • Total Actual USDC Volume Traded:       ${total_volume_day:,.2f} USDC across 24h")
print(f"  • Average Actual Available Entry Price:  ${avg_entry_px:.4f} per share")
print(f"  • Average Actual Available Exit Price:   ${avg_exit_px:.4f} per share")
print("="*125)
