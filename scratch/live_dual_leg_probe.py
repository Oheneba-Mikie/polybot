import requests
import json
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

# Current 5m window
now_ts = int(time.time())
w_s = (now_ts // 300) * 300
w_e = w_s + 300
slug = f"btc-updown-5m-{w_s}"

print("="*105)
print(f"🔴 LIVE DUAL-LEG ARBITRAGE PROBE ON CURRENT MARKET ({slug})")
print("="*105)

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}").json()
if not r or not r[0].get("markets"):
    print("Market not found on Gamma API!")
    sys.exit(1)

mkt = r[0]["markets"][0]
clob_ids = json.loads(mkt.get("clobTokenIds"))
up_tid = clob_ids[0]
down_tid = clob_ids[1]
strike = float(mkt.get("description", "").split("$")[1].split(" ")[0].replace(",", "") if "$" in mkt.get("description", "") else 0.0)

print(f"Candle: {mkt.get('question')}")
print(f"Window Start: {datetime.datetime.fromtimestamp(w_s, datetime.timezone.utc).strftime('%H:%M:%S UTC')}")
print(f"Window End:   {datetime.datetime.fromtimestamp(w_e, datetime.timezone.utc).strftime('%H:%M:%S UTC')}\n")

# Stream order book depth on both tokens every 2 seconds until candle close
print(f"{'Time (UTC)':<12} | {'T-Left':<8} | {'BTC Gap':<10} | {'Best UP Ask (Vol)':<20} | {'Best DOWN Ask (Vol)':<20} | {'Combined Cost':<15} | {'Arb Status'}")
print("-" * 115)

simulated_up_fill = None
simulated_down_fill = None

while time.time() < w_e + 2:
    t_now = time.time()
    t_left = max(0.0, w_e - t_now)
    dt_str = datetime.datetime.fromtimestamp(t_now, datetime.timezone.utc).strftime('%H:%M:%S')
    
    # Query order books
    try:
        up_book = requests.get(f"{CLOB_HOST}/book?token_id={up_tid}", timeout=2).json()
        down_book = requests.get(f"{CLOB_HOST}/book?token_id={down_tid}", timeout=2).json()
        
        up_asks = up_book.get("asks", [])
        down_asks = down_book.get("asks", [])
        
        best_up_ask = float(up_asks[-1]["price"]) if up_asks else None
        best_up_vol = float(up_asks[-1]["size"]) if up_asks else 0.0
        
        best_down_ask = float(down_asks[-1]["price"]) if down_asks else None
        best_down_vol = float(down_asks[-1]["size"]) if down_asks else 0.0
        
        # Get live BTC price from Binance
        r_btc = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=2).json()
        live_btc = float(r_btc.get("price", 0.0))
        gap = live_btc - strike if strike > 0 else 0.0
        
        up_str = f"${best_up_ask:.3f} ({best_up_vol:,.0f} sh)" if best_up_ask is not None else "No Asks"
        down_str = f"${best_down_ask:.3f} ({best_down_vol:,.0f} sh)" if best_down_ask is not None else "No Asks"
        
        # Check if one or both legs can be bought
        if best_up_ask is not None and best_down_ask is not None:
            comb = best_up_ask + best_down_ask
            comb_str = f"${comb:.4f}"
            if comb < 1.00:
                arb_status = f"🔥 ARB OPPORTUNITY (+{(1.0-comb)/comb*100:.1f}%)"
            else:
                arb_status = "Spread > $1.00"
        else:
            comb_str = "N/A"
            arb_status = "One Book Dry"
            
        gap_str = f"${gap:+,.1f}" if strike > 0 else "N/A"
        print(f"{dt_str:<12} | T-{t_left:<5.1f}s | {gap_str:<10} | {up_str:<20} | {down_str:<20} | {comb_str:<15} | {arb_status}")
        
    except Exception as e:
        print(f"{dt_str:<12} | Error querying books: {e}")
        
    time.sleep(2.0)

print("="*115)
print("🏁 CANDLE RESOLUTION REACHED")
print("="*115)
