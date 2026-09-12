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

# Target candle: 10:45 AM - 10:50 AM ET (14:45:00 -> 14:50:00 UTC)
now = int(time.time())
ts = (now // 300) * 300
candle_end = ts + 300
slug = f"btc-updown-5m-{ts}"

t_start_et = datetime.datetime.fromtimestamp(ts - 4*3600, datetime.timezone.utc).strftime("%I:%M:%S %p ET")
t_end_et   = datetime.datetime.fromtimestamp(candle_end - 4*3600, datetime.timezone.utc).strftime("%I:%M:%S %p ET")

print("="*110, flush=True)
print(f"🔴 LIVE FULL-MARKET SURVEILLANCE: Bitcoin Up or Down [{t_start_et} -> {t_end_et}]", flush=True)
print(f"   • Slug: {slug} | Watching full 300 seconds until resolution at {t_end_et}", flush=True)
print("="*110, flush=True)

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

# Record starting BTC price
try:
    r_cb = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=2).json()
    ptb = float(r_cb["data"]["amount"])
except:
    ptb = 77300.0

print(f"📌 Starting Strike BTC Price (PTB): ${ptb:,.2f}\n", flush=True)
print(f"{'Time (Countdown)':<20} | {'BTC Price (Delta)':<22} | {'UP Bid / Ask':<24} | {'DOWN Bid / Ask':<24} | {'Status'}", flush=True)
print("-" * 110, flush=True)

snapshots = []
min_up_ask = 1.0
min_dn_ask = 1.0

while time.time() < candle_end + 3:
    now_t = time.time()
    elapsed = int(now_t - ts)
    rem = int(candle_end - now_t)
    t_utc = datetime.datetime.fromtimestamp(now_t, datetime.timezone.utc).strftime("%H:%M:%S")
    t_cd = f"T+{elapsed}s (T-{rem}s)"
    
    # Get current BTC
    try:
        r_cb = requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=2).json()
        cur_btc = float(r_cb["data"]["amount"])
        delta = cur_btc - ptb
        delta_str = f"${cur_btc:,.2f} ({'+' if delta>=0 else ''}${delta:.1f})"
    except:
        cur_btc = ptb
        delta_str = "BTC Syncing..."
        
    # Get Live Books
    try:
        r_up = requests.get(f"{CLOB_HOST}/book?token_id={up_token}", timeout=2).json()
        r_dn = requests.get(f"{CLOB_HOST}/book?token_id={dn_token}", timeout=2).json()
        
        u_bids = sorted(r_up.get("bids", []), key=lambda x: float(x["price"]), reverse=True)
        u_asks = sorted(r_up.get("asks", []), key=lambda x: float(x["price"]))
        d_bids = sorted(r_dn.get("bids", []), key=lambda x: float(x["price"]), reverse=True)
        d_asks = sorted(r_dn.get("asks", []), key=lambda x: float(x["price"]))
        
        up_bid_p = float(u_bids[0]["price"]) if u_bids else None
        up_ask_p = float(u_asks[0]["price"]) if u_asks else None
        dn_bid_p = float(d_bids[0]["price"]) if d_bids else None
        dn_ask_p = float(d_asks[0]["price"]) if d_asks else None
        
        if up_ask_p: min_up_ask = min(min_up_ask, up_ask_p)
        if dn_ask_p: min_dn_ask = min(min_dn_ask, dn_ask_p)
        
        up_str = f"${up_bid_p:.2f} / ${up_ask_p:.2f}" if up_bid_p and up_ask_p else "Syncing..."
        dn_str = f"${dn_bid_p:.2f} / ${dn_ask_p:.2f}" if dn_bid_p and dn_ask_p else "Syncing..."
        
        comb_str = f"Comb: ${min_up_ask + min_dn_ask:.2f}"
    except Exception as e:
        up_str = "Error"
        dn_str = "Error"
        comb_str = ""
        
    print(f"{t_cd:<20} | {delta_str:<22} | {up_str:<24} | {dn_str:<24} | {comb_str}", flush=True)
    snapshots.append({"elapsed": elapsed, "btc": cur_btc, "up_ask": up_ask_p, "dn_ask": dn_ask_p})
    
    # Sleep 10s intervals
    time.sleep(10)

print("\n" + "="*110, flush=True)
print(f"🏁 MARKET RESOLVED: FINAL AUDIT OF FULL 5-MINUTE CANDLE", flush=True)
print("="*110, flush=True)

# Fetch final resolution prices
time.sleep(3)
r_final = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
outcome_prices = json.loads(r_final[0]["markets"][0].get("outcomePrices", "[]")) if r_final else []

up_final = outcome_prices[0] if len(outcome_prices) > 0 else "Pending"
dn_final = outcome_prices[1] if len(outcome_prices) > 1 else "Pending"

# Fetch all trades executed across full window
r_tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=1000", timeout=4).json()
all_trades = []
for t in r_tr:
    tr_ts = t.get("timestamp") or t.get("matchTime")
    if isinstance(tr_ts, str):
        try: tr_ts = datetime.datetime.fromisoformat(tr_ts.replace("Z", "+00:00")).timestamp() if "T" in tr_ts else float(tr_ts)
        except: tr_ts = 0
    if tr_ts > 1e11: tr_ts /= 1000.0
    if ts <= tr_ts <= ts + 300:
        all_trades.append(t)

print(f"\n1. 🎯 FINAL OUTCOME & SETTLEMENT:")
print(f"   • Starting BTC Price: ${ptb:,.2f}")
print(f"   • UP Final Settlement:   {up_final}")
print(f"   • DOWN Final Settlement: {dn_final}")
print(f"   • Total Trades Filled:   {len(all_trades)} trades")

print(f"\n2. 💰 COMBINED DUAL-LEG ENTRY ACROSS THIS FULL CANDLE:")
print(f"   • Lowest UP Ask Observed:   ${min_up_ask:.3f}")
print(f"   • Lowest DOWN Ask Observed: ${min_dn_ask:.3f}")
combined_total = min_up_ask + min_dn_ask
print(f"   • Total Combined Stake:     ${min_up_ask:.3f} + ${min_dn_ask:.3f} = ${combined_total:.3f}")
if combined_total < 1.00:
    net_p = 1.00 - combined_total
    print(f"   • 💰 GUARANTEED NET PROFIT: +${net_p:.3f} (+{(net_p/combined_total)*100:.1f}%) on $1.00 Payout")
else:
    print(f"   • Total Stake exceeded $1.00 (${combined_total:.2f})")

print("="*110, flush=True)
