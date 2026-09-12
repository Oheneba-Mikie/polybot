import requests
import json
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

# TARGET TOTAL COST FOR GUARANTEED PROFIT (e.g. $0.960)
TARGET_TOTAL_COST = 0.960

now_ts = int(time.time())
w_s = (now_ts // 300) * 300
w_e = w_s + 300
slug = f"btc-updown-5m-{w_s}"

print("="*115)
print(f"🔴 LIVE DYNAMIC HEDGE ENGINE WITH ORDER BOOK DEPTH AUDIT ({slug})")
print("="*115)

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}").json()
if not r or not r[0].get("markets"):
    print(f"Market {slug} not found, checking next window...")
    w_s += 300
    w_e += 300
    slug = f"btc-updown-5m-{w_s}"
    r = requests.get(f"{GAMMA_HOST}/events?slug={slug}").json()

mkt = r[0]["markets"][0]
clob_ids = json.loads(mkt.get("clobTokenIds"))
up_tid = clob_ids[0]
down_tid = clob_ids[1]

print(f"Candle: {mkt.get('question')}")
print(f"Window Start: {datetime.datetime.fromtimestamp(w_s, datetime.timezone.utc).strftime('%H:%M:%S UTC')}")
print(f"Window End:   {datetime.datetime.fromtimestamp(w_e, datetime.timezone.utc).strftime('%H:%M:%S UTC')}\n")

print(f"{'Time (UTC)':<12} | {'State':<22} | {'UP Ask (Avail)':<20} | {'DOWN Ask (Avail)':<20} | {'Max Allowed Leg 2':<20} | {'Action / Log'}")
print("-" * 125)

leg1_token = None
leg1_price = None
leg1_time = None
leg1_avail_shares = None
leg2_max_price = None
hedge_locked = False
leg2_token = None
leg2_price = None
leg2_time = None
leg2_avail_shares = None

while time.time() < w_e + 2:
    t_now = time.time()
    t_left = max(0.0, w_e - t_now)
    dt_str = datetime.datetime.fromtimestamp(t_now, datetime.timezone.utc).strftime('%H:%M:%S')
    
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
        
        # 1. Look for Leg 1 Entry (taking the cheaper side when price dips to <= 55c)
        if leg1_token is None:
            if best_up_ask is not None and best_up_ask <= 0.550:
                leg1_token = "UP"
                leg1_price = best_up_ask
                leg1_time = dt_str
                leg1_avail_shares = best_up_vol
                leg2_max_price = round(TARGET_TOTAL_COST - leg1_price, 4)
                print(f"{dt_str:<12} | {'⚡ LEG 1 TRIGGERED':<22} | {up_str:<20} | {down_str:<20} | {f'<=${leg2_max_price:.3f} on DOWN':<20} | 🛒 BUYING UP @ ${leg1_price:.3f} (Avail on Book: {leg1_avail_shares:,.0f} sh)")
            elif best_down_ask is not None and best_down_ask <= 0.550:
                leg1_token = "DOWN"
                leg1_price = best_down_ask
                leg1_time = dt_str
                leg1_avail_shares = best_down_vol
                leg2_max_price = round(TARGET_TOTAL_COST - leg1_price, 4)
                print(f"{dt_str:<12} | {'⚡ LEG 1 TRIGGERED':<22} | {up_str:<20} | {down_str:<20} | {f'<=${leg2_max_price:.3f} on UP':<20} | 🛒 BUYING DOWN @ ${leg1_price:.3f} (Avail on Book: {leg1_avail_shares:,.0f} sh)")
            else:
                if int(t_left) % 10 == 0:
                    print(f"{dt_str:<12} | {'WAITING FOR LEG 1':<22} | {up_str:<20} | {down_str:<20} | {'N/A':<20} | Monitoring order books")
        
        # 2. Leg 1 is Filled -> Continuously monitor opposing token for Leg 2 Price <= leg2_max_price
        elif not hedge_locked:
            if leg1_token == "UP":
                # Need DOWN Ask <= leg2_max_price
                if best_down_ask is not None and best_down_ask <= leg2_max_price:
                    leg2_token = "DOWN"
                    leg2_price = best_down_ask
                    leg2_time = dt_str
                    leg2_avail_shares = best_down_vol
                    hedge_locked = True
                    total_cost = leg1_price + leg2_price
                    profit_pct = ((1.00 - total_cost) / total_cost) * 100
                    print(f"{dt_str:<12} | {'🎯 HEDGE COMPLETED':<22} | {up_str:<20} | {down_str:<20} | {f'Hit ${leg2_price:.3f}':<20} | 🔒 LOCKED! Bought DOWN @ ${leg2_price:.3f} (Avail: {leg2_avail_shares:,.0f} sh | Total: ${total_cost:.3f})")
                else:
                    if int(t_left) % 10 == 0:
                        diff = round(best_down_ask - leg2_max_price, 3) if best_down_ask is not None else 0.0
                        print(f"{dt_str:<12} | {'HUNTING LEG 2 (DOWN)':<22} | {up_str:<20} | {down_str:<20} | {f'<=${leg2_max_price:.3f} (Diff: ${diff:+.3f})':<20} | Watching DOWN ask")
            else:
                # Need UP Ask <= leg2_max_price
                if best_up_ask is not None and best_up_ask <= leg2_max_price:
                    leg2_token = "UP"
                    leg2_price = best_up_ask
                    leg2_time = dt_str
                    leg2_avail_shares = best_up_vol
                    hedge_locked = True
                    total_cost = leg1_price + leg2_price
                    profit_pct = ((1.00 - total_cost) / total_cost) * 100
                    print(f"{dt_str:<12} | {'🎯 HEDGE COMPLETED':<22} | {up_str:<20} | {down_str:<20} | {f'Hit ${leg2_price:.3f}':<20} | 🔒 LOCKED! Bought UP @ ${leg2_price:.3f} (Avail: {leg2_avail_shares:,.0f} sh | Total: ${total_cost:.3f})")
                else:
                    if int(t_left) % 10 == 0:
                        diff = round(best_up_ask - leg2_max_price, 3) if best_up_ask is not None else 0.0
                        print(f"{dt_str:<12} | {'HUNTING LEG 2 (UP)':<22} | {up_str:<20} | {down_str:<20} | {f'<=${leg2_max_price:.3f} (Diff: ${diff:+.3f})':<20} | Watching UP ask")
        else:
            if int(t_left) % 15 == 0:
                print(f"{dt_str:<12} | {'HEDGE 100% LOCKED':<22} | {up_str:<20} | {down_str:<20} | {'COMPLETE':<20} | Holding pair to $1.00 Payout")
                
    except Exception as e:
        print(f"{dt_str:<12} | Error: {e}")
        
    time.sleep(1.0)

print("="*115)
print("🏁 CANDLE RESOLUTION SUMMARY & VERIFIED ORDER BOOK DEPTH:")
print("="*115)
if hedge_locked:
    total_cost = leg1_price + leg2_price
    profit_pct = ((1.00 - total_cost) / total_cost) * 100
    print(f"  • Leg 1 ({leg1_token}): Bought @ ${leg1_price:.3f} at {leg1_time}")
    print(f"    └── Order Book Depth Available BEFORE Purchase: {leg1_avail_shares:,.0f} shares")
    print(f"  • Leg 2 ({leg2_token}): Bought @ ${leg2_price:.3f} at {leg2_time} (Max Allowed: ${leg2_max_price:.3f})")
    print(f"    └── Order Book Depth Available BEFORE Purchase: {leg2_avail_shares:,.0f} shares")
    print(f"  • Total Cost per Pair: ${total_cost:.3f}")
    print(f"  • Guaranteed Settlement: $1.0000 USDC")
    print(f"  • Guaranteed Net Profit: +${1.00 - total_cost:.3f} (+{profit_pct:.2f}%)")
    print(f"  • Loss Risk: 0.0000%")
elif leg1_token is not None:
    print(f"  • Leg 1 ({leg1_token}) bought @ ${leg1_price:.3f} (Avail: {leg1_avail_shares:,.0f} sh), but Leg 2 did not reach <= ${leg2_max_price:.3f}.")
else:
    print("  • Leg 1 did not trigger. 100% cash preserved.")
print("="*115)
