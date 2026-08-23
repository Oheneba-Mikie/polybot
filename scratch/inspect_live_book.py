import os
import sys
import json
import time
import requests

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST = "https://clob.polymarket.com"

# Find active 5m BTC market
now = time.time()
w_s = int(now // 300) * 300
slug = f"btc-updown-5m-{w_s}"

print(f"=== QUERYING POLYMARKET LIVE ORDER BOOK FOR: {slug} ===\n")

r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}").json()
if not r_evt or not r_evt[0].get("markets"):
    print("Market not found, querying upcoming...")
    r_evt = requests.get(f"{GAMMA_HOST}/events?limit=10&active=true&closed=false").json()

m = None
for evt in r_evt:
    if "btc" in evt.get("slug", ""):
        m = evt.get("markets", [])[0]
        break

if not m:
    print("No active BTC market found.")
    sys.exit(0)

clob_tokens = json.loads(m.get("clobTokenIds", "[]"))
outcomes = json.loads(m.get("outcomes", "[]"))
up_id, dn_id = clob_tokens[0], clob_tokens[1]

print(f"Market Question : {m.get('question')}")
print(f"Condition ID    : {m.get('conditionId')}")
print(f"Min Order Size  : {m.get('orderMinSize', 'N/A')}")
print(f"Min Tick Size   : {m.get('orderPriceMinTickSize', 'N/A')}\n")

# Fetch full order books
r_up = requests.get(f"{CLOB_HOST}/book?token_id={up_id}").json()
r_dn = requests.get(f"{CLOB_HOST}/book?token_id={dn_id}").json()

up_bids = r_up.get("bids", [])
up_asks = r_up.get("asks", [])
dn_bids = r_dn.get("bids", [])
dn_asks = r_dn.get("asks", [])

print("="*65)
print(f"{'UP TOKEN ORDER BOOK':^65}")
print("="*65)
print(f"{'BIDS (Size @ Price)':<30} | {'ASKS (Price @ Size)':<30}")
print("-"*65)
max_rows = max(len(up_bids), len(up_asks), 5)
for i in range(min(max_rows, 8)):
    b_str = f"{float(up_bids[i]['size']):.1f} sh @ ${float(up_bids[i]['price']):.3f}" if i < len(up_bids) else "-"
    a_str = f"${float(up_asks[i]['price']):.3f} @ {float(up_asks[i]['size']):.1f} sh" if i < len(up_asks) else "-"
    print(f"{b_str:<30} | {a_str:<30}")

print("\n" + "="*65)
print(f"{'DOWN TOKEN ORDER BOOK':^65}")
print("="*65)
print(f"{'BIDS (Size @ Price)':<30} | {'ASKS (Price @ Size)':<30}")
print("-"*65)
max_rows = max(len(dn_bids), len(dn_asks), 5)
for i in range(min(max_rows, 8)):
    b_str = f"{float(dn_bids[i]['size']):.1f} sh @ ${float(dn_bids[i]['price']):.3f}" if i < len(dn_bids) else "-"
    a_str = f"${float(dn_asks[i]['price']):.3f} @ {float(dn_asks[i]['size']):.1f} sh" if i < len(dn_asks) else "-"
    print(f"{b_str:<30} | {a_str:<30}")

best_up_bid = float(up_bids[0]['price']) if up_bids else None
best_up_ask = float(up_asks[0]['price']) if up_asks else None
best_dn_bid = float(dn_bids[0]['price']) if dn_bids else None
best_dn_ask = float(dn_asks[0]['price']) if dn_asks else None

print("\n" + "="*65)
print("ANALYSIS OF RESTING LIMIT BIDS & SPREAD:")
print("="*65)
if best_up_bid and best_dn_bid:
    print(f"Top Bids Sum : UP Bid (${best_up_bid:.3f}) + DOWN Bid (${best_dn_bid:.3f}) = ${best_up_bid + best_dn_bid:.4f}")
if best_up_ask and best_dn_ask:
    print(f"Top Asks Sum : UP Ask (${best_up_ask:.3f}) + DOWN Ask (${best_dn_ask:.3f}) = ${best_up_ask + best_dn_ask:.4f}")
print("="*65)
