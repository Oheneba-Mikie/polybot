import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

# 1. Fetch live 5m market slug
now = time.time()
w_s = int(now // 300) * 300
slug = f"btc-updown-5m-{w_s}"

print("="*105)
print(f"📊 LIVE POLYMARKET CLOB ORDER BOOK SNAPSHOT FOR CURRENT CANDLE: {slug}")
print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(now))}")
print("="*105)

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()

if not r or not r[0].get("markets"):
    print("Market event not found, trying previous candle...")
    slug = f"btc-updown-5m-{w_s - 300}"
    r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()

mkt = r[0]["markets"][0]
title = mkt.get("question")
clob_ids = json.loads(mkt.get("clobTokenIds") or "[]")
outs = json.loads(mkt.get("outcomes") or "[]")

print(f"Market Question: {title}")
print(f"Active Outcomes: {outs}")
print(f"CLOB Token IDs:  {clob_ids}\n")

for idx, tid in enumerate(clob_ids):
    out_name = outs[idx] if idx < len(outs) else f"Outcome {idx}"
    print(f"\n" + "="*85)
    print(f"🎯 ORDER BOOK DEPTH FOR OUTCOME: [{out_name.upper()}] (Token ID: {tid[:16]}...)")
    print("="*85)
    
    b_res = requests.get(f"{CLOB_HOST}/book", params={"token_id": tid}, timeout=5).json()
    bids = b_res.get("bids", [])
    asks = b_res.get("asks", [])
    
    sorted_bids = sorted(bids, key=lambda x: float(x["price"]), reverse=True)
    sorted_asks = sorted(asks, key=lambda x: float(x["price"]))
    
    print(f"--- 🟢 TOP 10 BIDS (BUYERS AVAILABLE) ---")
    print(f"{'Level':<6} | {'Bid Price ($)':<15} | {'Size (Shares)':<15} | {'Total Value (USDC)'}")
    print("-" * 65)
    for i, b in enumerate(sorted_bids[:10]):
        p = float(b["price"])
        sz = float(b["size"])
        val = p * sz
        print(f"#{i+1:<5} | ${p:<14.3f} | {sz:<14.1f} | ${val:,.2f}")
        
    print(f"\n--- 🔴 TOP 10 ASKS (SELLERS AVAILABLE TO BUY FROM) ---")
    print(f"{'Level':<6} | {'Ask Price ($)':<15} | {'Size (Shares)':<15} | {'Total Value (USDC)'}")
    print("-" * 65)
    for i, a in enumerate(sorted_asks[:10]):
        p = float(a["price"])
        sz = float(a["size"])
        val = p * sz
        print(f"#{i+1:<5} | ${p:<14.3f} | {sz:<14.1f} | ${val:,.2f}")
        
    total_ask_sz = sum(float(a["size"]) for a in sorted_asks)
    total_ask_val = sum(float(a["size"]) * float(a["price"]) for a in sorted_asks)
    print(f"\nTOTAL Resting Ask Liquidity on Book: {total_ask_sz:,.1f} shares (${total_ask_val:,.2f} USDC)")

print("\n" + "="*105)
