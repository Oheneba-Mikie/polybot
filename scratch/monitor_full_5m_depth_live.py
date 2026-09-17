import requests
import json
import time
import datetime
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

# Target candle: 7:05 PM - 7:10 PM ET (23:05:00 -> 23:10:00 UTC)
now_ts = int(time.time())
ts = (now_ts // 300) * 300
candle_end = ts + 300
slug = f"btc-updown-5m-{ts}"

t_start_et = datetime.datetime.fromtimestamp(ts - 4*3600, datetime.timezone.utc).strftime("%I:%M:%S %p ET")
t_end_et   = datetime.datetime.fromtimestamp(candle_end - 4*3600, datetime.timezone.utc).strftime("%I:%M:%S %p ET")

print("="*115, flush=True)
print(f"🔴 LIVE CONTINUOUS 5-MINUTE DEPTH SURVEILLANCE: [{t_start_et} -> {t_end_et}]", flush=True)
print(f"   • Market Slug: {slug}", flush=True)
print(f"   • Tracking exact share depth on both sides every 10 seconds until {t_end_et}", flush=True)
print("="*115, flush=True)

# Resolve tokens
r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
if not r or not r[0].get("markets"):
    print("Market not found")
    sys.exit(0)

mkt = r[0]["markets"][0]
cid = mkt.get("conditionId")
tokens = json.loads(mkt.get("clobTokenIds", "[]"))
outcomes = json.loads(mkt.get("outcomes", "[]"))

up_token = tokens[0]
dn_token = tokens[1]
if len(outcomes) >= 2 and outcomes[0].lower() not in ("up", "yes"):
    up_token, dn_token = tokens[1], tokens[0]

print(f"\n{'Time (Countdown)':<20} | {'UP Level 1 (Ask & Size)':<26} | {'DOWN Level 1 (Ask & Size)':<28} | {'Combined Pair':<15} | {'Instant Executable Depth'}", flush=True)
print("-" * 115, flush=True)

snapshots = []

while time.time() < candle_end + 3:
    now_t = time.time()
    elapsed = int(now_t - ts)
    rem = int(candle_end - now_t)
    t_cd = f"T+{elapsed}s (T-{rem}s)"
    
    try:
        r_up = requests.get(f"{CLOB_HOST}/book?token_id={up_token}", timeout=2).json()
        r_dn = requests.get(f"{CLOB_HOST}/book?token_id={dn_token}", timeout=2).json()
        
        u_asks = sorted(r_up.get("asks", []), key=lambda x: float(x["price"]))
        d_asks = sorted(r_dn.get("asks", []), key=lambda x: float(x["price"]))
        
        u_px = float(u_asks[0]["price"]) if u_asks else None
        u_sz = float(u_asks[0]["size"]) if u_asks else 0.0
        d_px = float(d_asks[0]["price"]) if d_asks else None
        d_sz = float(d_asks[0]["size"]) if d_asks else 0.0
        
        # Calculate instant pair cost & executable depth at same second
        if u_px is not None and d_px is not None:
            comb_cost = u_px + d_px
            max_instant_pairs = min(u_sz, d_sz)
            cost_str = f"${comb_cost:.3f}"
            depth_str = f"{max_instant_pairs:,.1f} pairs (${max_instant_pairs * comb_cost:,.2f})"
        else:
            comb_cost = None
            cost_str = "One-Sided"
            depth_str = "-"
            
        u_str = f"${u_px:.3f} ({u_sz:,.1f} sh)" if u_px is not None else "-"
        d_str = f"${d_px:.3f} ({d_sz:,.1f} sh)" if d_px is not None else "-"
        
        print(f"{t_cd:<20} | {u_str:<26} | {d_str:<28} | {cost_str:<15} | {depth_str}", flush=True)
        snapshots.append({
            "elapsed": elapsed,
            "up_px": u_px, "up_sz": u_sz,
            "dn_px": d_px, "dn_sz": d_sz,
            "comb_cost": comb_cost,
            "max_pairs": min(u_sz, d_sz) if u_px and d_px else 0
        })
    except Exception as e:
        print(f"{t_cd:<20} | Error fetching books: {e}", flush=True)
        
    time.sleep(10)

print("\n" + "="*115, flush=True)
print("🏁 FULL 5-MINUTE CANDLE CONCLUDED: AUDIT SUMMARY", flush=True)
print("="*115, flush=True)

# Fetch outcome
time.sleep(3)
r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
outcome_prices = json.loads(r_evt[0]["markets"][0].get("outcomePrices", "[]")) if r_evt else []

print(f"1. 🎯 FINAL SETTLEMENT: UP = {outcome_prices[0] if outcome_prices else 'N/A'} | DOWN = {outcome_prices[1] if len(outcome_prices)>1 else 'N/A'}")

# Analyze depth across snapshots
valid_snaps = [s for s in snapshots if s["comb_cost"] is not None]
if valid_snaps:
    avg_up_depth = sum(s["up_sz"] for s in valid_snaps) / len(valid_snaps)
    avg_dn_depth = sum(s["dn_sz"] for s in valid_snaps) / len(valid_snaps)
    avg_instant_pairs = sum(s["max_pairs"] for s in valid_snaps) / len(valid_snaps)
    min_comb = min(s["comb_cost"] for s in valid_snaps)
    
    print(f"\n2. 📊 AVERAGE SAME-MILLISECOND DEPTH:")
    print(f"   • Average UP Shares Available at Level 1:   {avg_up_depth:,.1f} shares")
    print(f"   • Average DOWN Shares Available at Level 1: {avg_dn_depth:,.1f} shares")
    print(f"   • Average Instantaneous Pair Depth (Min of Both): {avg_instant_pairs:,.1f} pairs")
    print(f"   • Lowest Combined Pair Cost Observed:       ${min_comb:.3f}")
    
print("="*115, flush=True)
