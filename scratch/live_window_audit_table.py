import requests
import json
import time
import datetime
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

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
    print("Could not find active 5m market.")
    exit(1)

print(f"=== LIVE AUDIT: {mkt['title']} ({mkt['slug']}) ===")
print("Tracking 25 consecutive live orderbook ticks...")

history = []
last_state = None
state_start_time = time.time()

for i in range(30):
    t_now = time.time()
    now_int = int(t_now)
    t_rem = max(0, mkt["window_end"] - now_int)
    t_str = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    
    try:
        r_up = requests.get(f"{CLOB_HOST}/book?token_id={mkt['up_token']}", timeout=2).json()
        r_dn = requests.get(f"{CLOB_HOST}/book?token_id={mkt['down_token']}", timeout=2).json()
        
        asks_up = r_up.get("asks", [])
        asks_dn = r_dn.get("asks", [])
        
        best_up = min(asks_up, key=lambda x: float(x["price"])) if asks_up else None
        best_dn = min(asks_dn, key=lambda x: float(x["price"])) if asks_dn else None
        
        up_p = float(best_up["price"]) if best_up else 1.0
        up_s = float(best_up["size"]) if best_up else 0.0
        dn_p = float(best_dn["price"]) if best_dn else 1.0
        dn_s = float(best_dn["size"]) if best_dn else 0.0
        
        comb = round(up_p + dn_p, 3)
        current_tuple = (up_p, round(up_s, 1), dn_p, round(dn_s, 1))
        
        if last_state is not None and current_tuple != last_state:
            duration = round(t_now - state_start_time, 1)
            history[-1]["duration"] = duration
            state_start_time = t_now
        
        history.append({
            "idx": i + 1,
            "time": t_str,
            "t_rem": t_rem,
            "up_p": up_p,
            "up_s": up_s,
            "dn_p": dn_p,
            "dn_s": dn_s,
            "comb": comb,
            "min_depth": min(up_s, dn_s),
            "duration": None
        })
        last_state = current_tuple
    except Exception as e:
        print("Fetch error:", e)
    
    time.sleep(0.5)

# Final duration for last state
if history and history[-1]["duration"] is None:
    history[-1]["duration"] = round(time.time() - state_start_time, 1)

print("\n--- FORMATTED AUDIT TABLE ---")
print("Tick | Time (UTC) | Candle Rem | UP Best Ask (Shares) | DOWN Best Ask (Shares) | Combined Ask | Both >= 100sh? | Pool Wiped In")
print("-" * 125)

for h in history:
    dur_str = f"Dried up in {h['duration']}s" if h['duration'] is not None else "Active"
    depth_check = "✅ YES" if h['min_depth'] >= 100.0 else f"❌ NO ({h['min_depth']:.0f} sh)"
    profit_tag = " [SUB-$1.00 CROSS!]" if h['comb'] <= 0.980 else ""
    print(f"{h['idx']:02d}   | {h['time']}   | T-{h['t_rem']:03d}s     | {h['up_s']:7.1f} sh @ ${h['up_p']:.2f}   | {h['dn_s']:7.1f} sh @ ${h['dn_p']:.2f}     | ${h['comb']:.3f}{profit_tag:18s} | {depth_check:14s} | {dur_str}")
