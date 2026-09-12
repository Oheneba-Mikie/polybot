import requests
import json
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

now = time.time()
cur_w_s = int(now // 300) * 300
cur_w_e = cur_w_s + 300
time_left = cur_w_e - now
slug = f"btc-updown-5m-{cur_w_s}"

print("="*90)
print(f"🔍 LIVE MARKET INSPECTION AT {datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M:%S UTC')}")
print("="*90)
print(f"Active Candle: {slug} ({time_left:.1f}s remaining)")

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
if r and r[0].get("markets"):
    mkt = r[0]["markets"][0]
    print(f"Question: {mkt.get('question')}")
    tids = json.loads(mkt.get("clobTokenIds", "[]"))
    up_id, dn_id = tids[0], tids[1]
    
    # Query order books
    r_up = requests.get(f"{CLOB_HOST}/book?token_id={up_id}", timeout=2).json()
    r_dn = requests.get(f"{CLOB_HOST}/book?token_id={dn_id}", timeout=2).json()
    
    up_asks = r_up.get("asks", [])
    dn_asks = r_dn.get("asks", [])
    
    best_up_ask = min([float(a['price']) for a in up_asks]) if up_asks else None
    best_dn_ask = min([float(a['price']) for a in dn_asks]) if dn_asks else None
    
    print(f"\nOrder Book Asks:")
    print(f"- UP Token Best Ask:   ${best_up_ask:.4f}" if best_up_ask else "- UP Token: No Asks")
    print(f"- DOWN Token Best Ask: ${best_dn_ask:.4f}" if best_dn_ask else "- DOWN Token: No Asks")

# Query Railway Dashboard State
try:
    r_dash = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=3).json()
    print("\nLive Railway Bot State:")
    print(f"- Status:       {r_dash.get('status')}")
    print(f"- Wallet Cash:  ${r_dash.get('balance')}")
    print(f"- Total Snipes: {r_dash.get('total_trades')}")
    print(f"- Recent Logs:")
    for l in r_dash.get("logs", [])[-5:]:
        print(f"  {l}")
except Exception as e:
    print(f"Dashboard error: {e}")

print("="*90)
