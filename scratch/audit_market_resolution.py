import requests
import json
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

ts = 1787487000
slug = f"btc-updown-5m-{ts}"

print("="*90)
print(f"📊 COMPREHENSIVE POLYMARKET AUDIT FOR MARKET: {slug}")
print("="*90)

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()
if not r or not r[0].get("markets"):
    print("Market not found!")
    sys.exit(0)

mkt = r[0]["markets"][0]
cid = mkt.get("conditionId")
title = mkt.get("question")
outcomes = json.loads(mkt.get("outcomes", "[]"))
clob_token_ids = json.loads(mkt.get("clobTokenIds", "[]"))
end_date = mkt.get("endDate")
closed = mkt.get("closed")
resolved = mkt.get("resolved")
resolution_source = mkt.get("resolutionSource")
outcome_prices = json.loads(mkt.get("outcomePrices", "[]"))

print(f"Question:            {title}")
print(f"Condition ID:        {cid}")
print(f"Outcomes:            {outcomes}")
print(f"Closed / Resolved:   Closed={closed}, Resolved={resolved}")
print(f"Final Resolv Prices: {outcome_prices}")
if outcome_prices:
    up_res = float(outcome_prices[0])
    dn_res = float(outcome_prices[1]) if len(outcome_prices) > 1 else 0.0
    winner = "UP (1.00)" if up_res == 1.0 else ("DOWN (1.00)" if dn_res == 1.0 else "Unresolved / Split")
    print(f"🏆 Final Resolution: {winner}")

print("\n" + "-"*90)
print("📜 ALL TRADES ON THIS MARKET (CHRONOLOGICAL):")
print("-"*90)
print(f"{'Timestamp (UTC)':<20} | {'Outcome':<6} | {'Price':<8} | {'Shares':<10} | {'Maker / Taker'}")
print("-"*90)

r_trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=200", timeout=5).json()
trades = sorted(r_trades, key=lambda x: x.get("timestamp", 0))

for t in trades:
    ts_sec = t.get("timestamp", 0)
    dt = datetime.datetime.fromtimestamp(ts_sec, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    side = t.get("outcome", "")
    px = float(t.get("price", 0))
    sz = float(t.get("size", 0))
    side_type = t.get("side", "")
    print(f"{dt:<20} | {side:<6} | ${px:<7.4f} | {sz:<10.2f} | {side_type}")

print("="*90)
