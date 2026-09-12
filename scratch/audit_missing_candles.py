import requests
import json
import datetime
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

print("="*95)
print(f"📊 FORENSIC AUDIT OF RECENT 5-MINUTE CANDLES (12:30-12:35 & 12:35-12:40 UTC)")
print("="*95)

# 1. Fetch Railway Bot logs
r_state = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=4).json()
print("📜 LATEST 20 RAILWAY BOT LOGS:")
for l in r_state.get("logs", [])[-20:]:
    print(f"   {l}")

# 2. Audit 12:30-12:35 and 12:35-12:40 on Polymarket
for slug, label in [
    ("btc-updown-5m-1787747400", "12:30 - 12:35 UTC"),
    ("btc-updown-5m-1787747700", "12:35 - 12:40 UTC"),
    ("btc-updown-5m-1787748000", "12:40 - 12:45 UTC (ACTIVE)")
]:
    r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}").json()
    if r_evt and r_evt[0].get("markets"):
        mkt = r_evt[0]["markets"][0]
        q = mkt.get("question")
        prices = json.loads(mkt.get("outcomePrices") or "[]")
        tids = json.loads(mkt.get("clobTokenIds", "[]"))
        up_id, dn_id = tids[0], tids[1]
        
        r_up = requests.get(f"{CLOB_HOST}/book?token_id={up_id}").json()
        r_dn = requests.get(f"{CLOB_HOST}/book?token_id={dn_id}").json()
        
        up_bids = [float(b["price"]) for b in r_up.get("bids", [])]
        up_asks = [float(a["price"]) for a in r_up.get("asks", [])]
        dn_bids = [float(b["price"]) for b in r_dn.get("bids", [])]
        dn_asks = [float(a["price"]) for a in r_dn.get("asks", [])]
        
        best_up_bid = max(up_bids) if up_bids else 0.0
        best_up_ask = min(up_asks) if up_asks else None
        best_dn_bid = max(dn_bids) if dn_bids else 0.0
        best_dn_ask = min(dn_asks) if dn_asks else None
        
        print(f"\n📁 {label} | Slug: {slug}")
        print(f"   Question: {q}")
        print(f"   Outcome Prices: {prices}")
        print(f"   🟢 UP Token:   Top Bid: ${best_up_bid:.4f} | Best Ask: ${best_up_ask if best_up_ask is not None else 0.0:.4f} ({len(up_asks)} asks on book)")
        print(f"   🔴 DOWN Token: Top Bid: ${best_dn_bid:.4f} | Best Ask: ${best_dn_ask if best_dn_ask is not None else 0.0:.4f} ({len(dn_asks)} asks on book)")

print("="*95)
