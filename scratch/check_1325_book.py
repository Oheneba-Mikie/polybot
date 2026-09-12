import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

slug = "btc-updown-5m-1787750700"
r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}").json()
if r_evt and r_evt[0].get("markets"):
    mkt = r_evt[0]["markets"][0]
    tids = json.loads(mkt.get("clobTokenIds", "[]"))
    up_id, dn_id = tids[0], tids[1]
    
    r_up = requests.get(f"{CLOB_HOST}/book?token_id={up_id}").json()
    r_dn = requests.get(f"{CLOB_HOST}/book?token_id={dn_id}").json()
    
    up_bids = [float(b["price"]) for b in r_up.get("bids", [])]
    up_asks = [float(a["price"]) for a in r_up.get("asks", [])]
    dn_bids = [float(b["price"]) for b in r_dn.get("bids", [])]
    dn_asks = [float(a["price"]) for a in r_dn.get("asks", [])]
    
    print(f"Window: 13:25 - 13:30 UTC ({slug})")
    print(f"🟢 UP Token:   Top Bid: {max(up_bids) if up_bids else 0.0:.4f} | Best Ask: {min(up_asks) if up_asks else 'NONE'} ({len(up_asks)} asks)")
    print(f"🔴 DOWN Token: Top Bid: {max(dn_bids) if dn_bids else 0.0:.4f} | Best Ask: {min(dn_asks) if dn_asks else 'NONE'} ({len(dn_asks)} asks)")
