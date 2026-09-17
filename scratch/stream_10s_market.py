import requests
import json
import time
import datetime

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

def get_active_market():
    now = int(time.time())
    cur_w = (now // 300) * 300
    for w in [cur_w, cur_w + 300]:
        slug = f"btc-updown-5m-{w}"
        try:
            r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
            if r and r[0].get("markets"):
                m = r[0]["markets"][0]
                tokens = json.loads(m.get("clobTokenIds", "[]"))
                if len(tokens) >= 2 and now < (w + 300):
                    return {
                        "slug": slug,
                        "title": r[0].get("title", slug),
                        "window_start": w,
                        "window_end": w + 300,
                        "up_token": tokens[0],
                        "down_token": tokens[1]
                    }
        except Exception:
            pass
    return None

mkt = get_active_market()
if not mkt:
    print("Could not find active market.")
    exit(1)

print(f"=== MONITORING: {mkt['title']} ({mkt['slug']}) ===")
print("Time | TimeRem | UP Best Bid | UP Best Ask | DOWN Best Bid | DOWN Best Ask | Sum Best Asks | Sum Best Bids")
print("-" * 105)

for i in range(10):
    now = int(time.time())
    t_rem = max(0, mkt["window_end"] - now)
    t_str = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    
    try:
        r_up = requests.get(f"{CLOB_HOST}/book?token_id={mkt['up_token']}", timeout=2).json()
        r_dn = requests.get(f"{CLOB_HOST}/book?token_id={mkt['down_token']}", timeout=2).json()
        
        asks_up = r_up.get("asks", [])
        bids_up = r_up.get("bids", [])
        asks_dn = r_dn.get("asks", [])
        bids_dn = r_dn.get("bids", [])
        
        # In CLOB, lowest ask is min(asks), highest bid is max(bids)
        best_up_ask = min(asks_up, key=lambda x: float(x["price"])) if asks_up else None
        best_up_bid = max(bids_up, key=lambda x: float(x["price"])) if bids_up else None
        
        best_dn_ask = min(asks_dn, key=lambda x: float(x["price"])) if asks_dn else None
        best_dn_bid = max(bids_dn, key=lambda x: float(x["price"])) if bids_dn else None
        
        up_ask_p = float(best_up_ask["price"]) if best_up_ask else 1.0
        up_ask_s = float(best_up_ask["size"]) if best_up_ask else 0.0
        up_bid_p = float(best_up_bid["price"]) if best_up_bid else 0.0
        up_bid_s = float(best_up_bid["size"]) if best_up_bid else 0.0
        
        dn_ask_p = float(best_dn_ask["price"]) if best_dn_ask else 1.0
        dn_ask_s = float(best_dn_ask["size"]) if best_dn_ask else 0.0
        dn_bid_p = float(best_dn_bid["price"]) if best_dn_bid else 0.0
        dn_bid_s = float(best_dn_bid["size"]) if best_dn_bid else 0.0
        
        sum_asks = up_ask_p + dn_ask_p
        sum_bids = up_bid_p + dn_bid_p
        
        print(f"{t_str} | T-{t_rem:03d}s | UP: ${up_bid_p:.2f} ({up_bid_s:5.0f}s) | UP: ${up_ask_p:.2f} ({up_ask_s:5.0f}s) | DN: ${dn_bid_p:.2f} ({dn_bid_s:5.0f}s) | DN: ${dn_ask_p:.2f} ({dn_ask_s:5.0f}s) | Asks: ${sum_asks:.3f} | Bids: ${sum_bids:.3f}")
    except Exception as e:
        print(f"{t_str} | Error: {e}")
        
    time.sleep(1.0)
