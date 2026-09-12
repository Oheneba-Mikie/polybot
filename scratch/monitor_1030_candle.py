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

# Target candle: 10:30 AM - 10:35 AM ET (14:30:00 -> 14:35:00 UTC)
ts = 1789223400
slug = f"btc-updown-5m-{ts}"

now_ts = int(time.time())
elapsed = now_ts - ts
remaining = 300 - elapsed

print("="*105, flush=True)
print(f"🔴 LIVE SCAN: Bitcoin Up or Down - September 12, 10:30AM-10:35AM ET", flush=True)
print(f"   • Slug: {slug} | Time Elapsed: T+{elapsed}s (T-{remaining}s remaining)", flush=True)
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

# 1. Fetch Live Order Books
r_up = requests.get(f"{CLOB_HOST}/book?token_id={up_token}", timeout=3).json()
r_dn = requests.get(f"{CLOB_HOST}/book?token_id={dn_token}", timeout=3).json()

u_bids = r_up.get("bids", [])
u_asks = r_up.get("asks", [])
d_bids = r_dn.get("bids", [])
d_asks = r_dn.get("asks", [])

# Sort bids descending, asks ascending
u_bids_sorted = sorted(u_bids, key=lambda x: float(x["price"]), reverse=True)
u_asks_sorted = sorted(u_asks, key=lambda x: float(x["price"]))
d_bids_sorted = sorted(d_bids, key=lambda x: float(x["price"]), reverse=True)
d_asks_sorted = sorted(d_asks, key=lambda x: float(x["price"]))

print(f"\n1. 📖 LIVE ORDER BOOK DEPTH RIGHT NOW:", flush=True)
print(f"   • UP Token:   Top Bid = ${float(u_bids_sorted[0]['price']):.3f} ({float(u_bids_sorted[0]['size']):.1f} sh) | Top Ask = ${float(u_asks_sorted[0]['price']):.3f} ({float(u_asks_sorted[0]['size']):.1f} sh)" if u_bids_sorted and u_asks_sorted else "   • UP Token: Order book syncing...")
print(f"   • DOWN Token: Top Bid = ${float(d_bids_sorted[0]['price']):.3f} ({float(d_bids_sorted[0]['size']):.1f} sh) | Top Ask = ${float(d_asks_sorted[0]['price']):.3f} ({float(d_asks_sorted[0]['size']):.1f} sh)" if d_bids_sorted and d_asks_sorted else "   • DOWN Token: Order book syncing...")

if u_asks_sorted and d_asks_sorted:
    comb_ask = float(u_asks_sorted[0]['price']) + float(d_asks_sorted[0]['price'])
    print(f"   • Instantaneous Combined Ask Cost: ${comb_ask:.3f}", flush=True)

# 2. Fetch all public trades executed in this candle so far
r_tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=200", timeout=3).json()

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
        candle_trades.append({"time": t_str, "ts": tr_ts, "sec": int(tr_ts - ts), "side": side, "outcome": outcome, "px": px, "sz": sz})

candle_trades.sort(key=lambda x: x["ts"])

print(f"\n2. 📊 EXECUTED TRADES SO FAR ({len(candle_trades)} fills during the first {elapsed} seconds):", flush=True)

up_fills = [t for t in candle_trades if t["outcome"] in ("UP", "YES")]
dn_fills = [t for t in candle_trades if t["outcome"] in ("DOWN", "NO")]

min_up = min(t["px"] for t in up_fills) if up_fills else None
max_up = max(t["px"] for t in up_fills) if up_fills else None
min_dn = min(t["px"] for t in dn_fills) if dn_fills else None
max_dn = max(t["px"] for t in dn_fills) if dn_fills else None

print(f"   • UP Shares Traded:   Total = {sum(t['sz'] for t in up_fills):.1f} sh | Min = ${min_up} | Max = ${max_up} ({len(up_fills)} fills)", flush=True)
print(f"   • DOWN Shares Traded: Total = {sum(t['sz'] for t in dn_fills):.1f} sh | Min = ${min_dn} | Max = ${max_dn} ({len(dn_fills)} fills)", flush=True)

if min_up is not None and min_dn is not None:
    comb = min_up + min_dn
    print(f"\n3. 🎯 COMBINED LOWEST ENTRY IN THIS CANDLE SO FAR:", flush=True)
    print(f"   • ${min_up:.3f} (UP) + ${min_dn:.3f} (DOWN) = ${comb:.3f} Total Cost per Pair", flush=True)
    if comb < 1.00:
        print(f"   • 💰 LOCKED PROFIT: +{((1.0 - comb)/comb)*100:.1f}% (Spent ${comb:.2f} -> Redeems $1.00 at 10:35 AM ET)", flush=True)
    else:
        print(f"   • Market currently balanced (Total = ${comb:.2f})", flush=True)

print(f"\n4. 📋 RECENT FILLS ON THIS CANDLE:", flush=True)
for t in candle_trades[-15:]:
    print(f"   [{t['time']}] (T+{t['sec']}s) {t['side']:<4} {t['sz']:>8.2f} sh {t['outcome']:<4} @ ${t['px']:.3f}", flush=True)

print("="*105, flush=True)
