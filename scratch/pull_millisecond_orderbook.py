import requests
import json
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

print("="*95)
print("🔍 PULLING MILLISECOND-BY-MILLISECOND POLYMARKET ORDER BOOK (0.98 - 0.99 MARKETS):")
print("="*95)

now = time.time()
cur_w_s = int(now // 300) * 300

# Get active 5-minute Bitcoin market
slug = f"btc-updown-5m-{cur_w_s}"
print(f"Connecting to live market: {slug}...")

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()
if not r or not r[0].get("markets"):
    print("Could not find market:", slug)
    sys.exit(0)

mkt = r[0]["markets"][0]
clob_token_ids = json.loads(mkt.get("clobTokenIds", "[]"))
outcomes = json.loads(mkt.get("outcomes", "[]"))

up_id = clob_token_ids[0] if len(clob_token_ids) > 0 else None
dn_id = clob_token_ids[1] if len(clob_token_ids) > 1 else None

print(f"UP Token ID:   {up_id[:20]}...")
print(f"DOWN Token ID: {dn_id[:20]}...")
print("\nSampling order book stream (10 snapshots, 200ms intervals):")
print("-" * 95)
print(f"{'Timestamp (UTC.ms)':<24} | {'Side':<4} | {'Best Bid':<9} | {'Bid Shares':<12} | {'Best Ask':<9} | {'Ask Shares':<12} | {'Spread'}")
print("-" * 95)

for i in range(12):
    t_now = time.time()
    dt = datetime.datetime.fromtimestamp(t_now, datetime.timezone.utc)
    ms_str = dt.strftime("%H:%M:%S") + f".{int(dt.microsecond / 1000):03d}"
    
    # Check UP token
    try:
        r_up = requests.get(f"{CLOB_HOST}/book?token_id={up_id}", timeout=2).json()
        bids = r_up.get("bids", [])
        asks = r_up.get("asks", [])
        
        top_bid = float(bids[0]["price"]) if bids else 0.0
        top_bid_sz = float(bids[0]["size"]) if bids else 0.0
        top_ask = float(asks[0]["price"]) if asks else 0.0
        top_ask_sz = float(asks[0]["size"]) if asks else 0.0
        spread = round(top_ask - top_bid, 4) if (top_bid and top_ask) else 0.0
        
        side_tag = "UP"
        print(f"[{ms_str}] | {side_tag:<4} | ${top_bid:<8.4f} | {top_bid_sz:<12.1f} | ${top_ask:<8.4f} | {top_ask_sz:<12.1f} | ${spread:.4f}")
        
    except Exception as e:
        print(f"[{ms_str}] Error: {e}")
        
    time.sleep(0.25)

print("="*95)
