import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*105)
print("🔍 24-HOUR SURGE AUDIT: WHERE THEORETICAL SURGES PROMISED WINS VS WHERE THEY CRASHED")
print("="*105)

# Fetch 1-minute BTC bars from Binance for the past 24 hours (1440 bars)
end_time = int(time.time() * 1000)
start_time = end_time - (24 * 60 * 60 * 1000)

url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={start_time}&endTime={end_time}&limit=1000"
res = requests.get(url).json()

if len(res) == 1000:
    last_t = res[-1][0]
    res2 = requests.get(f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={last_t + 60000}&endTime={end_time}&limit=1000").json()
    res.extend(res2)

print(f"Loaded {len(res)} 1-minute bars covering the last 24 hours.")

# Group into 5-minute candles (288 total)
candles_5m = []
curr_block = []

for bar in res:
    bar_ts = int(bar[0]) // 1000
    if bar_ts % 300 == 0:
        if len(curr_block) == 5:
            candles_5m.append(curr_block)
        curr_block = [bar]
    else:
        if curr_block:
            curr_block.append(bar)

if len(curr_block) == 5:
    candles_5m.append(curr_block)

print(f"Analyzed {len(candles_5m)} complete 5-minute candles.\n")

# Audit every candle with a $25 surge
surge_threshold = 25.0
surge_trades = []

total_surges = 0
surges_that_held = 0
surges_that_reversed = 0

reversal_details = []

for c in candles_5m:
    strike = float(c[0][1])
    high_5m = max(float(b[2]) for b in c)
    low_5m = min(float(b[3]) for b in c)
    close_5m = float(c[4][4])
    t12_price = float(c[4][4]) # Price at end of 4th minute (T-12s)
    
    dt_str = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(int(c[0][0]) // 1000))
    
    # Check if an early surge happened (in bars 1, 2, or 3)
    early_high = max(float(b[2]) for b in c[:3])
    early_low  = min(float(b[3]) for b in c[:3])
    
    early_up_surge = (early_high - strike) >= surge_threshold
    early_dn_surge = (strike - early_low) >= surge_threshold
    
    final_winner = "UP" if close_5m > strike else "DOWN"
    
    if early_up_surge:
        total_surges += 1
        if final_winner == "UP":
            surges_that_held += 1
        else:
            surges_that_reversed += 1
            reversal_details.append({
                "time": dt_str,
                "surge_side": "UP",
                "strike": strike,
                "peak_surge": early_high - strike,
                "final_close": close_5m,
                "final_loss_gap": close_5m - strike,
                "t12_winner": "DOWN" if (t12_price - strike) < 0 else "UP"
            })
            
    elif early_dn_surge:
        total_surges += 1
        if final_winner == "DOWN":
            surges_that_held += 1
        else:
            surges_that_reversed += 1
            reversal_details.append({
                "time": dt_str,
                "surge_side": "DOWN",
                "strike": strike,
                "peak_surge": -(strike - early_low),
                "final_close": close_5m,
                "final_loss_gap": close_5m - strike,
                "t12_winner": "UP" if (t12_price - strike) > 0 else "DOWN"
            })

print(f"📈 24-HOUR SURGE SUMMARY (Total 5m Windows: {len(candles_5m)}):")
print(f"  • Total Early $25 Surges Triggered:      {total_surges}")
print(f"  • Surges That Held to the End (Won):     {surges_that_held} ({(surges_that_held/total_surges*100):.1f}%)")
print(f"  • Surges That REVERSED & FAILED (Lost):  {surges_that_reversed} ({(surges_that_reversed/total_surges*100):.1f}%)\n")

print("="*105)
print("🚨 THE EXACT SURGE TRAPS WHERE THE EARLY CODE BOUGHT AND LOST IN THE LAST 24 HOURS:")
print("="*105)
for idx, r in enumerate(reversal_details, 1):
    print(f"  [{idx:02d}] {r['time']} | Bought: {r['surge_side']:<4} (Surged: ${r['peak_surge']:+.2f}) -> BUT REVERSED to Close ${r['final_close']:.2f} ({r['final_loss_gap']:+.2f}) [WIPEOUT!]")
    print(f"       -> What Tier 2 at T-12s saw: True Winner was {r['t12_winner']}")

print("="*105)
