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

# Target candle: 10:40 AM - 10:45 AM ET (14:40:00 -> 14:45:00 UTC)
now_ts = int(time.time())
w_s = (now_ts // 300) * 300
slug = f"btc-updown-5m-{w_s}"
elapsed = now_ts - w_s
remaining = 300 - elapsed

t_start_et = datetime.datetime.fromtimestamp(w_s - 4*3600, datetime.timezone.utc).strftime("%I:%M %p ET")
t_end_et   = datetime.datetime.fromtimestamp(w_s + 300 - 4*3600, datetime.timezone.utc).strftime("%I:%M %p ET")

print("="*105, flush=True)
print(f"🔴 LIVE ACTIVE CANDLE CHECK: {slug} ({t_start_et} -> {t_end_et})", flush=True)
print(f"   • Time Elapsed: T+{elapsed}s | Remaining: T-{remaining}s", flush=True)
print("="*105, flush=True)

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
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

# 1. Fetch Live CLOB Books Right Now
r_up = requests.get(f"{CLOB_HOST}/book?token_id={up_token}", timeout=3).json()
r_dn = requests.get(f"{CLOB_HOST}/book?token_id={dn_token}", timeout=3).json()

u_bids = r_up.get("bids", [])
u_asks = r_up.get("asks", [])
d_bids = r_dn.get("bids", [])
d_asks = r_dn.get("asks", [])

u_bids_sorted = sorted(u_bids, key=lambda x: float(x["price"]), reverse=True)
u_asks_sorted = sorted(u_asks, key=lambda x: float(x["price"]))
d_bids_sorted = sorted(d_bids, key=lambda x: float(x["price"]), reverse=True)
d_asks_sorted = sorted(d_asks, key=lambda x: float(x["price"]))

print(f"\n1. 📖 LIVE ORDER BOOK RIGHT NOW (At T+{elapsed}s):", flush=True)
if u_bids_sorted and u_asks_sorted:
    print(f"   • UP Token:   Top Bid = ${float(u_bids_sorted[0]['price']):.3f} ({float(u_bids_sorted[0]['size']):.1f} sh) | Top Ask = ${float(u_asks_sorted[0]['price']):.3f} ({float(u_asks_sorted[0]['size']):.1f} sh)")
if d_bids_sorted and d_asks_sorted:
    print(f"   • DOWN Token: Top Bid = ${float(d_bids_sorted[0]['price']):.3f} ({float(d_bids_sorted[0]['size']):.1f} sh) | Top Ask = ${float(d_asks_sorted[0]['price']):.3f} ({float(d_asks_sorted[0]['size']):.1f} sh)")

# 2. Fetch All Public Trades So Far in This Candle
r_tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=300", timeout=3).json()

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
    
    if w_s <= tr_ts <= w_s + 300:
        t_str = datetime.datetime.fromtimestamp(tr_ts, datetime.timezone.utc).strftime("%H:%M:%S")
        candle_trades.append({"time": t_str, "ts": tr_ts, "sec": int(tr_ts - w_s), "side": side, "outcome": outcome, "px": px, "sz": sz})

candle_trades.sort(key=lambda x: x["ts"])

print(f"\n2. 📊 EXECUTED TRADES IN THIS CANDLE ({len(candle_trades)} fills during first {elapsed}s):", flush=True)

up_fills = [t for t in candle_trades if t["outcome"] in ("UP", "YES")]
dn_fills = [t for t in candle_trades if t["outcome"] in ("DOWN", "NO")]

min_up = min(t["px"] for t in up_fills) if up_fills else None
max_up = max(t["px"] for t in up_fills) if up_fills else None
min_dn = min(t["px"] for t in dn_fills) if dn_fills else None
max_dn = max(t["px"] for t in dn_fills) if dn_fills else None

print(f"   • UP Price Range Traded:   Min = ${min_up} | Max = ${max_up} ({len(up_fills)} trades)")
print(f"   • DOWN Price Range Traded: Min = ${min_dn} | Max = ${max_dn} ({len(dn_fills)} trades)")

if min_up is not None and min_dn is not None:
    comb = min_up + min_dn
    print(f"\n3. 🎯 DUAL-LEG COMBINATION IN THIS ACTIVE CANDLE:", flush=True)
    print(f"   • Lowest UP Fill:   ${min_up:.3f}")
    print(f"   • Lowest DOWN Fill: ${min_dn:.3f}")
    print(f"   • Combined Cost:    ${min_up:.3f} + ${min_dn:.3f} = ${comb:.3f}")
    if comb < 1.00:
        print(f"   • 💰 LOCKED PROFIT: +{((1.0 - comb)/comb)*100:.1f}% (Spent ${comb:.2f} -> Redeems $1.00 at {t_end_et})")
    else:
        print(f"   • Current sum: ${comb:.2f}")

print(f"\n4. 📋 CHRONOLOGICAL TRADE LOG SAMPLE ON THIS CANDLE:")
for t in candle_trades[:15]:
    print(f"   [{t['time']}] (T+{t['sec']}s) {t['side']:<4} {t['sz']:>8.2f} sh {t['outcome']:<4} @ ${t['px']:.3f}")

print("="*105, flush=True)
