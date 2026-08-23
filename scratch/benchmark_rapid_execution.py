import os
import time
import datetime
import requests
import json
import sys
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv("d:/Desktop/antigravity/POLYBOT/polybot/scalper_bailout_deploy/.env")

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2 import OrderArgs, MarketOrderArgsV2, OrderType

print("="*90)
print("⚡ MILLISECOND HIGH-FREQUENCY BUY/SELL LATENCY BENCHMARK:")
print("="*90)

WALLET = "0x89B489569F1B2384ee02E958444aF6091219bfe9"
client = ClobClient(
    host="https://clob.polymarket.com",
    key=os.getenv("POLYMARKET_PRIVATE_KEY"),
    chain_id=137,
    signature_type=2,
    funder=WALLET
)
client.set_api_creds(client.create_or_derive_api_key())

# Get active market token
now = time.time()
cur_w_s = int(now // 300) * 300
slug = f"btc-updown-5m-{cur_w_s}"
r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=5).json()
mkt = r[0]["markets"][0]
clob_tokens = json.loads(mkt.get("clobTokenIds", "[]"))
up_token = clob_tokens[0]

print(f"Target Market Token: {up_token[:20]}...")
print("\n--- PHASE 1: ORDER SIGNING & ENCODING SPEED (10 ITERATIONS) ---")
sign_times = []
for i in range(10):
    t0 = time.perf_counter()
    # Sign / encode order
    signed = client.create_order(OrderArgs(
        token_id=up_token,
        price=0.01,
        size=5.0,
        side="BUY"
    ))
    t1 = time.perf_counter()
    dt_ms = (t1 - t0) * 1000.0
    sign_times.append(dt_ms)
    print(f"Iteration #{i+1:02d}: {dt_ms:.2f} ms")

avg_sign = sum(sign_times) / len(sign_times)
print(f"Average Sign & Hash Speed: {avg_sign:.2f} ms ({1000.0/avg_sign:.0f} orders/second)")

print("\n--- PHASE 2: REST API NETWORK ROUNDTRIP (POST & CANCEL) ---")
api_latencies = []
for i in range(5):
    t0 = time.perf_counter()
    # Post order at low price 0.01 (safe, won't fill)
    post_res = client.post_order(signed, OrderType.GTC)
    t1 = time.perf_counter()
    post_ms = (t1 - t0) * 1000.0
    
    order_id = post_res.get("orderID") if isinstance(post_res, dict) else getattr(post_res, "orderID", None)
    
    # Cancel order immediately
    t2 = time.perf_counter()
    if order_id:
        client.cancel(order_id)
    t3 = time.perf_counter()
    cancel_ms = (t3 - t2) * 1000.0
    
    total_rt_ms = (t3 - t0) * 1000.0
    api_latencies.append(total_rt_ms)
    print(f"Roundtrip #{i+1:02d}: POST = {post_ms:.1f}ms | CANCEL = {cancel_ms:.1f}ms | Total RT = {total_rt_ms:.1f}ms")

avg_rt = sum(api_latencies) / len(api_latencies)
print(f"\nAverage Full Buy/Cancel Roundtrip Latency: {avg_rt:.2f} ms")
print(f"Theoretical Max Rapid Cycles: {1000.0 / avg_rt:.2f} full buy/sell operations per second")
print("="*90)
