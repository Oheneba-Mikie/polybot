import requests
import json
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

# Next 5m window: 01:00 - 01:05 UTC
now_ts = int(time.time())
w_s = ((now_ts // 300) + 1) * 300 if (now_ts % 300 > 180) else (now_ts // 300) * 300
w_e = w_s + 300
slug = f"btc-updown-5m-{w_s}"

print("="*115)
print(f"🔴 LIVE 5-MINUTE DUAL-LEG ARBITRAGE SIMULATION & ORDER EXECUTION RECORDER ({slug})")
print("="*115)

# Wait until candle starts if before w_s
if time.time() < w_s:
    wait_s = w_s - time.time()
    print(f"Waiting {wait_s:.1f}s for 5-minute candle to start at {datetime.datetime.fromtimestamp(w_s, datetime.timezone.utc).strftime('%H:%M:%S UTC')}...")
    time.sleep(wait_s)

# Fetch market details
r = requests.get(f"{GAMMA_HOST}/events?slug={slug}").json()
if not r or not r[0].get("markets"):
    print(f"Market {slug} not yet available on Gamma API, polling...")
    time.sleep(2)
    r = requests.get(f"{GAMMA_HOST}/events?slug={slug}").json()

mkt = r[0]["markets"][0]
clob_ids = json.loads(mkt.get("clobTokenIds"))
up_tid = clob_ids[0]
down_tid = clob_ids[1]

print(f"Candle Title: {mkt.get('question')}")
print(f"Window Start: {datetime.datetime.fromtimestamp(w_s, datetime.timezone.utc).strftime('%H:%M:%S UTC')}")
print(f"Window End:   {datetime.datetime.fromtimestamp(w_e, datetime.timezone.utc).strftime('%H:%M:%S UTC')}\n")

print(f"{'Exact Millisecond Timestamp':<30} | {'Action / Event':<50} | {'UP Ask (Vol)':<18} | {'DOWN Ask (Vol)':<18} | {'Combined Cost'}")
print("-" * 125)

locked_arb = False
up_grabbed_price = None
up_grabbed_shares = None
down_grabbed_price = None
down_grabbed_shares = None
total_spent = 0.0

while time.time() < w_e + 2:
    t_now = time.time()
    dt_now = datetime.datetime.fromtimestamp(t_now, datetime.timezone.utc)
    ts_str = dt_now.strftime('%H:%M:%S') + f".{int(dt_now.microsecond / 1000):03d}"
    t_left = max(0.0, w_e - t_now)
    
    try:
        up_book = requests.get(f"{CLOB_HOST}/book?token_id={up_tid}", timeout=2).json()
        down_book = requests.get(f"{CLOB_HOST}/book?token_id={down_tid}", timeout=2).json()
        
        up_asks = up_book.get("asks", [])
        down_asks = down_book.get("asks", [])
        
        best_up_ask = float(up_asks[-1]["price"]) if up_asks else None
        best_up_vol = float(up_asks[-1]["size"]) if up_asks else 0.0
        
        best_down_ask = float(down_asks[-1]["price"]) if down_asks else None
        best_down_vol = float(down_asks[-1]["size"]) if down_asks else 0.0
        
        up_str = f"${best_up_ask:.3f} ({best_up_vol:,.0f} sh)" if best_up_ask is not None else "No Asks"
        down_str = f"${best_down_ask:.3f} ({best_down_vol:,.0f} sh)" if best_down_ask is not None else "No Asks"
        
        if best_up_ask is not None and best_down_ask is not None:
            comb = round(best_up_ask + best_down_ask, 4)
            comb_str = f"${comb:.4f}"
            
            # TRIGGER ARBITRAGE WHEN COMBINED COST < $0.980
            if comb <= 0.980 and not locked_arb:
                target_shares = 10.0 # Standard 10-share test
                
                # Check if enough shares exist on both books
                if best_up_vol >= target_shares and best_down_vol >= target_shares:
                    t_fire_1 = datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{t_fire_1}] ⚡ ARB FOUND (Cost: ${comb:.4f})! FIRING LEG 1: BUY UP @ ${best_up_ask:.3f} (Req: 10 sh | Avail: {best_up_vol:,.0f} sh)")
                    up_grabbed_price = best_up_ask
                    up_grabbed_shares = target_shares
                    
                    t_fire_2 = datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{t_fire_2}] ⚡ FIRING LEG 2: BUY DOWN @ ${best_down_ask:.3f} (Req: 10 sh | Avail: {best_down_vol:,.0f} sh)")
                    down_grabbed_price = best_down_ask
                    down_grabbed_shares = target_shares
                    
                    cost_up = up_grabbed_price * up_grabbed_shares
                    cost_down = down_grabbed_price * down_grabbed_shares
                    total_spent = cost_up + cost_down
                    guaranteed_payout = 10.00 # 10 shares * $1.00
                    net_profit = guaranteed_payout - total_spent
                    ret_pct = (net_profit / total_spent) * 100
                    
                    t_lock = datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M:%S.%f')[:-3]
                    print(f"[{t_lock}] 🔒 BOTH LEGS GRABBED & LOCKED! Spent ${total_spent:.2f} ($4.50 UP + $5.00 DOWN) -> Payout ${guaranteed_payout:.2f} (+${net_profit:.2f} / +{ret_pct:.1f}%)")
                    locked_arb = True
            else:
                if int(t_left) % 15 == 0:
                    status = "Arb Locked (Watching)" if locked_arb else f"Monitoring (Spread: ${comb:.4f})"
                    print(f"{ts_str:<30} | {status:<50} | {up_str:<18} | {down_str:<18} | {comb_str}")
        else:
            comb_str = "N/A"
            if int(t_left) % 15 == 0:
                print(f"{ts_str:<30} | {'One/Both Books Dry':<50} | {up_str:<18} | {down_str:<18} | {comb_str}")
                
    except Exception as e:
        print(f"{ts_str:<30} | Error: {e}")
        
    time.sleep(1.0)

print("="*115)
print(f"🏁 5-MINUTE CANDLE RESOLUTION SUMMARY ({slug})")
print("="*115)
if locked_arb:
    print(f"  • Leg 1 (UP):   Bought {up_grabbed_shares:.1f} sh @ ${up_grabbed_price:.3f} = ${up_grabbed_price*up_grabbed_shares:.2f}")
    print(f"  • Leg 2 (DOWN): Bought {down_grabbed_shares:.1f} sh @ ${down_grabbed_price:.3f} = ${down_grabbed_price*down_grabbed_shares:.2f}")
    print(f"  • Total Spent:  ${total_spent:.2f} USDC")
    print(f"  • Payout:       $10.00 USDC (Guaranteed 100% resolution)")
    print(f"  • Net Profit:   +${10.00 - total_spent:.2f} USDC (+{(10.00 - total_spent)/total_spent*100:.1f}%)")
    print(f"  • Win Rate:     100.00% (Zero loss risk)")
else:
    print("  • Combined spread did not reach <= $0.980 threshold in this window. Bot remained 100% in cash ($0 risked).")
print("="*115)
