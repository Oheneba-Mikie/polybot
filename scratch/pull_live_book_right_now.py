import requests
import json
import time
import datetime
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

now_ts = int(time.time())
w_s = (now_ts // 300) * 300
slug = f"btc-updown-5m-{w_s}"
elapsed = now_ts - w_s
remaining = 300 - elapsed

t_utc = datetime.datetime.fromtimestamp(now_ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
t_et  = datetime.datetime.fromtimestamp(now_ts - 4*3600, datetime.timezone.utc).strftime("%I:%M:%S %p ET")

print("="*110, flush=True)
print(f"🔴 LIVE POLYMARKET ORDER BOOK PULL: {slug}", flush=True)
print(f"   • Exact Current Time: {t_utc} ({t_et})", flush=True)
print(f"   • Candle Progress:    T+{elapsed}s elapsed (T-{remaining}s remaining)", flush=True)
print("="*110, flush=True)

# Resolve tokens
r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
if not r or not r[0].get("markets"):
    print("Active market not found")
    sys.exit(0)

mkt = r[0]["markets"][0]
print(f"📌 Market Title: {mkt.get('question')}\n", flush=True)

tokens = json.loads(mkt.get("clobTokenIds", "[]"))
outcomes = json.loads(mkt.get("outcomes", "[]"))

up_token = tokens[0]
dn_token = tokens[1]
if len(outcomes) >= 2 and outcomes[0].lower() not in ("up", "yes"):
    up_token, dn_token = tokens[1], tokens[0]

# Pull live books
r_up = requests.get(f"{CLOB_HOST}/book?token_id={up_token}", timeout=3).json()
r_dn = requests.get(f"{CLOB_HOST}/book?token_id={dn_token}", timeout=3).json()

u_asks = sorted(r_up.get("asks", []), key=lambda x: float(x["price"]))
d_asks = sorted(r_dn.get("asks", []), key=lambda x: float(x["price"]))
u_bids = sorted(r_up.get("bids", []), key=lambda x: float(x["price"]), reverse=True)
d_bids = sorted(r_dn.get("bids", []), key=lambda x: float(x["price"]), reverse=True)

print("📖 1. ASKS (SHARES AVAILABLE TO BUY RIGHT NOW):", flush=True)
print(f"{'Level':<8} | {'UP Shares for Sale':<20} | {'UP Price':<10} | {'DOWN Shares for Sale':<22} | {'DOWN Price':<12} | {'Combined Pair Cost'}")
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
        
    print(f"{lvl:<8} | {u_sz:<20} | {u_px:<10} | {d_sz:<22} | {d_px:<12} | {comb_str}", flush=True)

print("\n" + "="*110, flush=True)
print("📖 2. BIDS (BUYERS WAITING ON THE ORDER BOOK):", flush=True)
print(f"{'Level':<8} | {'UP Bids (Buyers)':<20} | {'UP Bid Price':<12} | {'DOWN Bids (Buyers)':<22} | {'DOWN Bid Price'}")
print("-" * 110, flush=True)

max_bid_rows = max(len(u_bids[:6]), len(d_bids[:6]))
for i in range(max_bid_rows):
    lvl = f"Level {i+1}"
    ub_sz = f"{float(u_bids[i]['size']):,.1f} shares" if i < len(u_bids) else "-"
    ub_px = f"${float(u_bids[i]['price']):.3f}" if i < len(u_bids) else "-"
    db_sz = f"{float(d_bids[i]['size']):,.1f} shares" if i < len(d_bids) else "-"
    db_px = f"${float(d_bids[i]['price']):.3f}" if i < len(d_bids) else "-"
    print(f"{lvl:<8} | {ub_sz:<20} | {ub_px:<12} | {db_sz:<22} | {db_px}", flush=True)

print("="*110, flush=True)
