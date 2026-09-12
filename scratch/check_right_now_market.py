import time
import datetime
import requests
import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

now = int(time.time())
dt_utc = datetime.datetime.fromtimestamp(now, datetime.timezone.utc)
dt_local = datetime.datetime.fromtimestamp(now)

print(f"Current System Time:")
print(f"  • UTC Time:   {dt_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
print(f"  • Local Time: {dt_local.strftime('%Y-%m-%d %H:%M:%S')}")

w_s = (now // 300) * 300
slug = f"btc-updown-5m-{w_s}"
print(f"\nCurrent 5-Minute BTC Market:")
print(f"  • Slug: {slug}")
print(f"  • Window: {datetime.datetime.fromtimestamp(w_s, datetime.timezone.utc).strftime('%H:%M:%S')} -> {datetime.datetime.fromtimestamp(w_s+300, datetime.timezone.utc).strftime('%H:%M:%S UTC')}")

try:
    r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=3).json()
    if r and r[0].get("markets"):
        mkt = r[0]["markets"][0]
        print(f"  • Market Title: {mkt.get('question')}")
        cid = mkt.get("conditionId")
        tokens = json.loads(mkt.get("clobTokenIds", "[]"))
        
        # Get live book
        if len(tokens) >= 2:
            r_up = requests.get(f"https://clob.polymarket.com/book?token_id={tokens[0]}", timeout=3).json()
            r_dn = requests.get(f"https://clob.polymarket.com/book?token_id={tokens[1]}", timeout=3).json()
            
            u_bids = r_up.get("bids", [])
            u_asks = r_up.get("asks", [])
            d_bids = r_dn.get("bids", [])
            d_asks = r_dn.get("asks", [])
            
            print(f"\nLive Order Book Right Now:")
            print(f"  • UP:   Bid ${u_bids[0]['price'] if u_bids else 'None'} ({u_bids[0]['size'] if u_bids else 0} sh) | Ask ${u_asks[0]['price'] if u_asks else 'None'} ({u_asks[0]['size'] if u_asks else 0} sh)")
            print(f"  • DOWN: Bid ${d_bids[0]['price'] if d_bids else 'None'} ({d_bids[0]['size'] if d_bids else 0} sh) | Ask ${d_asks[0]['price'] if d_asks else 'None'} ({d_asks[0]['size'] if d_asks else 0} sh)")
except Exception as e:
    print(f"Error: {e}")
