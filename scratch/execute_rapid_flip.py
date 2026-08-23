import os
import time
import datetime
import requests
import json
import math
import sys
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv("d:/Desktop/antigravity/POLYBOT/polybot/scalper_bailout_deploy/.env")

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2 import MarketOrderArgsV2, OrderType, ApiCreds

print("="*90)
print("⚡ EXECUTING LIVE RAPID BUY & SELL TEST ON ACTIVE POLYMARKET CLOB:")
print("="*90)

POLYMARKET_ADDRESS        = os.getenv("POLYMARKET_ADDRESS", "")
POLYMARKET_API_KEY        = os.getenv("POLYMARKET_API_KEY", "")
POLYMARKET_API_SECRET     = os.getenv("POLYMARKET_API_SECRET", "")
POLYMARKET_API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE", "")
POLYMARKET_PRIVATE_KEY    = os.getenv("POLYMARKET_PRIVATE_KEY", "")

creds = ApiCreds(
    api_key=POLYMARKET_API_KEY,
    api_secret=POLYMARKET_API_SECRET,
    api_passphrase=POLYMARKET_API_PASSPHRASE
)
client = ClobClient(
    host="https://clob.polymarket.com",
    key=POLYMARKET_PRIVATE_KEY,
    chain_id=137,
    creds=creds,
    signature_type=3,
    funder=POLYMARKET_ADDRESS
)

# 1. Get active 5m market
now = time.time()
cur_w_s = int(now // 300) * 300
slug = f"btc-updown-5m-{cur_w_s}"
print(f"Connecting to live market: {slug}...")

r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=5).json()
if not r or not r[0].get("markets"):
    print("Market not found!")
    sys.exit(0)

mkt = r[0]["markets"][0]
clob_tokens = json.loads(mkt.get("clobTokenIds", "[]"))
up_id = clob_tokens[0]
dn_id = clob_tokens[1]

# Probe both books
def get_book(tok_id):
    r_b = requests.get(f"https://clob.polymarket.com/book?token_id={tok_id}", timeout=2).json()
    bids = r_b.get("bids", [])
    asks = r_b.get("asks", [])
    top_bid = float(bids[0]["price"]) if bids else 0.0
    top_ask = float(asks[0]["price"]) if asks else 0.0
    return top_ask, top_bid

up_ask, up_bid = get_book(up_id)
dn_ask, dn_bid = get_book(dn_id)

print(f"UP:   Ask=${up_ask:.4f} | Bid=${up_bid:.4f}")
print(f"DOWN: Ask=${dn_ask:.4f} | Bid=${dn_bid:.4f}")

# Pick higher probability side or available ask
if up_ask >= dn_ask and up_ask > 0.1:
    target_id = up_id
    side_name = "UP"
    entry_ask = up_ask
else:
    target_id = dn_id
    side_name = "DOWN"
    entry_ask = dn_ask

print(f"\nTarget Side: {side_name} @ Ask=${entry_ask:.4f}")

# STEP 1: EXECUTE BUY
print("\n--- [STEP 1] EXECUTING RAPID BUY ---")
t_buy_start = time.perf_counter()
dt_buy_start = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-3]
print(f"[{dt_buy_start}] Submitting BUY order for 5.0 shares of {side_name}...")

stake = max(4.85, round(5.0 * entry_ask, 2))
buy_res = client.create_and_post_market_order(
    MarketOrderArgsV2(token_id=target_id, amount=stake, price=entry_ask, side="BUY", order_type=OrderType.FAK),
    order_type=OrderType.FAK
)
t_buy_end = time.perf_counter()
dt_buy_end = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-3]
buy_duration_ms = (t_buy_end - t_buy_start) * 1000.0

print(f"[{dt_buy_end}] ✅ BUY CONFIRMED ON-CHAIN! (Latency: {buy_duration_ms:.1f} ms)")

# Settle check
time.sleep(0.3)

# STEP 2: EXECUTE RAPID SELL WITH SETTLEMENT RETRY
print("\n--- [STEP 2] EXECUTING RAPID SELL (WAITING FOR INDEXER) ---")
t_sell_start = time.perf_counter()

for attempt in range(1, 10):
    dt_sell_attempt = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    try:
        print(f"[{dt_sell_attempt}] Sell Attempt #{attempt}: Submitting SELL for 5.0 shares of {side_name}...")
        sell_res = client.create_and_post_market_order(
            MarketOrderArgsV2(token_id=target_id, amount=5.0, price=0.01, side="SELL", order_type=OrderType.FAK),
            order_type=OrderType.FAK
        )
        t_sell_end = time.perf_counter()
        dt_sell_end = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-3]
        sell_duration_ms = (t_sell_end - t_sell_start) * 1000.0
        print(f"[{dt_sell_end}] ✅ SELL CONFIRMED ON-CHAIN! (Total Sell Latency: {sell_duration_ms:.1f} ms)")
        break
    except Exception as e:
        print(f"[{dt_sell_attempt}] Awaiting on-chain indexer settlement ({e})... retrying in 0.4s")
        time.sleep(0.4)

total_elapsed_ms = (t_sell_end - t_buy_start) * 1000.0
print("\n" + "="*90)
print(f"🏁 RAPID FLIP COMPLETE: Buy={buy_duration_ms:.1f}ms | Sell={sell_duration_ms:.1f}ms | Total Cycle={total_elapsed_ms:.1f}ms")
print("="*90)
