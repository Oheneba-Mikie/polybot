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

# Select window: 14:15:00 UTC -> 14:20:00 UTC (btc-updown-5m-1789222500)
# Also check 14:10:00 UTC -> 14:15:00 UTC (btc-updown-5m-1789222200)

target_ts = 1789222500 # 14:15 UTC
slug = f"btc-updown-5m-{target_ts}"

print("="*105, flush=True)
print(f"📊 SECOND-BY-SECOND SHARE AVAILABILITY AUDIT: {slug} (14:15:00 -> 14:20:00 UTC)", flush=True)
print("="*105, flush=True)

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
if not r or not r[0].get("markets"):
    print("Market not found")
    sys.exit(0)

mkt = r[0]["markets"][0]
cid = mkt.get("conditionId")

# Fetch all trades
r_tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=1000", timeout=4).json()

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
    
    if target_ts <= tr_ts <= target_ts + 300:
        trades.append({"ts": tr_ts, "sec": int(tr_ts - target_ts), "side": side, "outcome": outcome, "px": px, "sz": sz})

trades.sort(key=lambda x: x["ts"])

print(f"Total trades filled during this 5-minute candle: {len(trades)} trades", flush=True)

# Group by 10-second intervals or individual seconds
time_buckets = defaultdict(lambda: {"up_shares": 0.0, "dn_shares": 0.0, "up_pxs": [], "dn_pxs": []})

for t in trades:
    # 5-second bucket or second
    sec = t["sec"]
    bucket = (sec // 10) * 10
    if t["outcome"] in ("UP", "YES"):
        time_buckets[bucket]["up_shares"] += t["sz"]
        time_buckets[bucket]["up_pxs"].append(t["px"])
    elif t["outcome"] in ("DOWN", "NO"):
        time_buckets[bucket]["dn_shares"] += t["sz"]
        time_buckets[bucket]["dn_pxs"].append(t["px"])

print(f"\n{'Second (Countdown)':<22} | {'Time (UTC)':<11} | {'UP Shares Available / Price':<30} | {'DOWN Shares Available / Price':<30}")
print("-" * 105, flush=True)

min_up_so_far = 1.0
min_dn_so_far = 1.0

for b in range(0, 301, 10):
    t_utc = datetime.datetime.fromtimestamp(target_ts + b, datetime.timezone.utc).strftime("%H:%M:%S")
    t_countdown = f"T+{b}s (T-{300-b}s)"
    
    data = time_buckets[b]
    up_sh = data["up_shares"]
    dn_sh = data["dn_shares"]
    
    up_str = f"{up_sh:.1f} sh @ ${min(data['up_pxs']):.2f}-${max(data['up_pxs']):.2f}" if data["up_pxs"] else "- (No fills)"
    dn_str = f"{dn_sh:.1f} sh @ ${min(data['dn_pxs']):.2f}-${max(data['dn_pxs']):.2f}" if data["dn_pxs"] else "- (No fills)"
    
    if data["up_pxs"]: min_up_so_far = min(min_up_so_far, min(data["up_pxs"]))
    if data["dn_pxs"]: min_dn_so_far = min(min_dn_so_far, min(data["dn_pxs"]))
    
    print(f"{t_countdown:<22} | {t_utc:<11} | {up_str:<30} | {dn_str:<30}", flush=True)

print("-" * 105, flush=True)
print(f"🎯 SUMMARY OF SHARE AVAILABILITY & ENTRY COMBINATION:", flush=True)
total_up = sum(t["sz"] for t in trades if t["outcome"] in ("UP", "YES"))
total_dn = sum(t["sz"] for t in trades if t["outcome"] in ("DOWN", "NO"))

print(f"   • Total UP Shares Traded across candle:   {total_up:.1f} shares (Lowest Price: ${min_up_so_far:.3f})")
print(f"   • Total DOWN Shares Traded across candle: {total_dn:.1f} shares (Lowest Price: ${min_dn_so_far:.3f})")
if min_up_so_far < 1.0 and min_dn_so_far < 1.0:
    comb = min_up_so_far + min_dn_so_far
    print(f"   • Combined Cost to Stake 1 UP + 1 DOWN:   ${min_up_so_far:.3f} + ${min_dn_so_far:.3f} = ${comb:.3f}")
    print(f"   • Net Guaranteed Payout at Resolution:    ${comb:.3f} spent -> $1.00 collected (+{((1.0-comb)/comb)*100:.1f}%)")
    
last_trade_sec = max(t["sec"] for t in trades) if trades else 0
print(f"   • Last Trade Before Close:                 T+{last_trade_sec}s (T-{300-last_trade_sec}s before close)")
print("="*105, flush=True)
