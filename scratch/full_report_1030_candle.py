import requests
import json
import time
import datetime
import sys
from collections import defaultdict

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

# Target candle: 10:30 AM - 10:35 AM ET (14:30:00 -> 14:35:00 UTC)
ts = 1789223400
slug = f"btc-updown-5m-{ts}"
candle_end = ts + 300

print(f"Waiting for candle {slug} (10:30AM - 10:35AM ET) to reach close at {datetime.datetime.fromtimestamp(candle_end, datetime.timezone.utc).strftime('%H:%M:%S UTC')}...", flush=True)

while time.time() < candle_end + 3:
    rem = int(candle_end - time.time())
    if rem > 0:
        print(f"Candle active... T-{rem}s remaining until close...", flush=True)
        time.sleep(min(10, rem))
    else:
        time.sleep(2)

print("\n" + "="*110, flush=True)
print(f"🏁 10:30AM-10:35AM ET COMPLETE 5-MINUTE CANDLE REPORT ({slug})", flush=True)
print("="*110, flush=True)

# Fetch market data and final resolution
r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()
mkt = r_evt[0]["markets"][0] if r_evt else {}
cid = mkt.get("conditionId")
outcome_prices = json.loads(mkt.get("outcomePrices", "[]")) if mkt.get("outcomePrices") else []

up_final = float(outcome_prices[0]) if len(outcome_prices) > 0 else "Pending"
dn_final = float(outcome_prices[1]) if len(outcome_prices) > 1 else "Pending"

# Fetch all trades for this window
r_tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=1500", timeout=5).json()

trades = []
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
        trades.append({"ts": tr_ts, "sec": int(tr_ts - ts), "side": side, "outcome": outcome, "px": px, "sz": sz})

trades.sort(key=lambda x: x["ts"])

# Group by 10-second intervals
buckets = defaultdict(lambda: {"up_sh": 0.0, "dn_sh": 0.0, "up_px": [], "dn_px": []})
for t in trades:
    b = (t["sec"] // 10) * 10
    if t["outcome"] in ("UP", "YES"):
        buckets[b]["up_sh"] += t["sz"]
        buckets[b]["up_px"].append(t["px"])
    elif t["outcome"] in ("DOWN", "NO"):
        buckets[b]["dn_sh"] += t["sz"]
        buckets[b]["dn_px"].append(t["px"])

print(f"\n1. 🎯 FINAL RESOLUTION & TOTAL VOLUME:")
print(f"   • UP Final Price:   {up_final}")
print(f"   • DOWN Final Price: {dn_final}")
print(f"   • Total Trades Executed: {len(trades)} fills")
print(f"   • Total UP Volume:   {sum(t['sz'] for t in trades if t['outcome'] in ('UP', 'YES')):.1f} shares")
print(f"   • Total DOWN Volume: {sum(t['sz'] for t in trades if t['outcome'] in ('DOWN', 'NO')):.1f} shares")

print(f"\n2. ⏱️ 10-SECOND TIMELINE OF SHARE AVAILABILITY & PRICES ACROSS ALL 5 MINUTES:")
print(f"{'Time (Countdown)':<22} | {'Time (UTC)':<10} | {'UP Shares Available / Price Range':<34} | {'DOWN Shares Available / Price Range':<34}")
print("-" * 110, flush=True)

min_up = 1.0
min_dn = 1.0

for b in range(0, 301, 10):
    t_utc = datetime.datetime.fromtimestamp(ts + b, datetime.timezone.utc).strftime("%H:%M:%S")
    t_cd = f"T+{b}s (T-{300-b}s)"
    
    d = buckets[b]
    up_sh = d["up_sh"]
    dn_sh = d["dn_sh"]
    
    up_str = f"{up_sh:>8.1f} sh @ ${min(d['up_px']):.2f} - ${max(d['up_px']):.2f}" if d["up_px"] else "- (No fills)"
    dn_str = f"{dn_sh:>8.1f} sh @ ${min(d['dn_px']):.2f} - ${max(d['dn_px']):.2f}" if d["dn_px"] else "- (No fills)"
    
    if d["up_px"]: min_up = min(min_up, min(d["up_px"]))
    if d["dn_px"]: min_dn = min(min_dn, min(d["dn_px"]))
    
    print(f"{t_cd:<22} | {t_utc:<10} | {up_str:<34} | {dn_str:<34}", flush=True)

print("-" * 110, flush=True)

print(f"\n3. 💰 DUAL-LEG COMBINED ENTRY ANALYSIS:")
if min_up < 1.0 and min_dn < 1.0:
    combined = min_up + min_dn
    print(f"   • Lowest UP Buy Price:   ${min_up:.3f}")
    print(f"   • Lowest DOWN Buy Price: ${min_dn:.3f}")
    print(f"   • Combined Pair Cost:    ${min_up:.3f} + ${min_dn:.3f} = ${combined:.3f}")
    if combined < 1.0:
        payout = 1.00
        net_profit = payout - combined
        pct = (net_profit / combined) * 100.0
        print(f"   • Guaranteed Net Profit: +${net_profit:.3f} (+{pct:.1f}%) on $1.00 Payout")
    else:
        print(f"   • Total cost exceeded $1.00 (No wave arb)")

last_tr = max(t["sec"] for t in trades) if trades else 0
print(f"   • Liquidity Dry-Up Time: Last trade filled at T+{last_tr}s (T-{300-last_tr}s before close)")
print("="*110, flush=True)
