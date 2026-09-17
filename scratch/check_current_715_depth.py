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

# Target active candle: 7:15 PM - 7:20 PM ET (23:15:00 -> 23:20:00 UTC)
now_ts = int(time.time())
w_s = (now_ts // 300) * 300
slug = f"btc-updown-5m-{w_s}"
elapsed = now_ts - w_s
remaining = 300 - elapsed

t_utc = datetime.datetime.fromtimestamp(now_ts, datetime.timezone.utc).strftime("%H:%M:%S UTC")
t_et  = datetime.datetime.fromtimestamp(now_ts - 4*3600, datetime.timezone.utc).strftime("%I:%M:%S %p ET")

print("="*110, flush=True)
print(f"🔴 CURRENT ACTIVE CANDLE DEPTH CHECK: {slug} [{t_et} / {t_utc}]", flush=True)
print(f"   • Candle Progress: T+{elapsed}s elapsed | T-{remaining}s remaining", flush=True)
print("="*110, flush=True)

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
if not r or not r[0].get("markets"):
    print("Market not found")
    sys.exit(0)

mkt = r[0]["markets"][0]
print(f"📌 Market Title: {mkt.get('question')}\n", flush=True)

cid = mkt.get("conditionId")
tokens = json.loads(mkt.get("clobTokenIds", "[]"))
outcomes = json.loads(mkt.get("outcomes", "[]"))

up_token = tokens[0]
dn_token = tokens[1]
if len(outcomes) >= 2 and outcomes[0].lower() not in ("up", "yes"):
    up_token, dn_token = tokens[1], tokens[0]

# 1. Fetch Full Live Order Book Depth
r_up = requests.get(f"{CLOB_HOST}/book?token_id={up_token}", timeout=3).json()
r_dn = requests.get(f"{CLOB_HOST}/book?token_id={dn_token}", timeout=3).json()

u_asks = sorted(r_up.get("asks", []), key=lambda x: float(x["price"]))
d_asks = sorted(r_dn.get("asks", []), key=lambda x: float(x["price"]))
u_bids = sorted(r_up.get("bids", []), key=lambda x: float(x["price"]), reverse=True)
d_bids = sorted(r_dn.get("bids", []), key=lambda x: float(x["price"]), reverse=True)

print("📖 1. LIVE ASKS RIGHT NOW (SHARES AVAILABLE TO BUY):", flush=True)
print(f"{'Level':<8} | {'UP Shares Available':<22} | {'UP Price':<10} | {'DOWN Shares Available':<24} | {'DOWN Price':<12} | {'Total Cost per Pair'}")
print("-" * 110, flush=True)

max_rows = max(len(u_asks[:6]), len(d_asks[:6]))
for i in range(max_rows):
    lvl = f"Level {i+1}"
    u_sz = f"{float(u_asks[i]['size']):,.1f} shares" if i < len(u_asks) else "-"
    u_px = f"${float(u_asks[i]['price']):.3f}" if i < len(u_asks) else "-"
    d_sz = f"{float(d_asks[i]['size']):,.1f} shares" if i < len(d_asks) else "-"
    d_px = f"${float(d_asks[i]['price']):.3f}" if i < len(d_asks) else "-"
    
    if i < len(u_asks) and i < len(d_asks):
        comb = float(u_asks[i]['price']) + float(d_asks[i]['price'])
        comb_str = f"${comb:.3f} ({'+' if comb<1.0 else ''}{((1.0-comb)/comb)*100:.1f}%)"
    else:
        comb_str = "-"
        
    print(f"{lvl:<8} | {u_sz:<22} | {u_px:<10} | {d_sz:<24} | {d_px:<12} | {comb_str}", flush=True)

# 2. Total Liquidity Available across all levels
total_up_depth = sum(float(x['size']) for x in u_asks)
total_dn_depth = sum(float(x['size']) for x in d_asks)
print(f"\n📊 TOTAL ORDER BOOK DEPTH:")
print(f"   • Total UP Shares Available on Book:   {total_up_depth:,.1f} shares")
print(f"   • Total DOWN Shares Available on Book: {total_dn_depth:,.1f} shares")

# 3. Fetch Executed Trades in this current candle
r_tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=100", timeout=3).json()
candle_trades = []
for t in r_tr:
    tr_ts = t.get("timestamp") or t.get("matchTime")
    if isinstance(tr_ts, str):
        try: tr_ts = datetime.datetime.fromisoformat(tr_ts.replace("Z", "+00:00")).timestamp() if "T" in tr_ts else float(tr_ts)
        except: tr_ts = 0
    if tr_ts > 1e11: tr_ts /= 1000.0
    if w_s <= tr_ts <= w_s + 300:
        candle_trades.append(t)

print(f"\n📋 RECENT FILLS ON THIS ACTIVE CANDLE ({len(candle_trades)} fills so far):", flush=True)
for t in candle_trades[:10]:
    out = str(t.get("outcome", "")).upper()
    sz = float(t.get("size", 0))
    px = float(t.get("price", 0))
    ts_fmt = datetime.datetime.fromtimestamp(t.get("timestamp", 0)/1000.0 if t.get("timestamp", 0)>1e11 else t.get("timestamp", 0), datetime.timezone.utc).strftime("%H:%M:%S")
    print(f"   [{ts_fmt}] BUY {sz:>7.1f} {out:<4} shares @ ${px:.3f} (Cost = ${sz*px:.2f})", flush=True)

print("="*110, flush=True)
