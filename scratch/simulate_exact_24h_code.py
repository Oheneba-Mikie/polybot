import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*115)
print("🔍 EXACT 24-HOUR CODE LOGIC SIMULATION (ALL 288 5-MINUTE CANDLES)")
print("="*115)

# Fetch 1-minute BTC bars from Binance for the past 24 hours (1440 bars)
end_time = int(time.time() * 1000)
start_time = end_time - (24 * 60 * 60 * 1000)

url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={start_time}&endTime={end_time}&limit=1000"
res = requests.get(url).json()

if len(res) == 1000:
    last_t = res[-1][0]
    res2 = requests.get(f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={last_t + 60000}&endTime={end_time}&limit=1000").json()
    res.extend(res2)

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

print(f"{'#':<3} | {'Time (UTC)':<16} | {'Strike':<10} | {'Trigger':<12} | {'Side':<4} | {'Entry Px':<9} | {'Exit Event':<28} | {'PnL':<8} | {'Result'}")
print("-" * 115)

total_sim_trades = 0
total_sim_wins = 0
total_sim_losses = 0
total_sim_profit = 0.0

for idx, c in enumerate(candles_5m, 1):
    dt_str = time.strftime("%Y-%m-%d %H:%M", time.gmtime(int(c[0][0]) // 1000))
    strike = float(c[0][1])
    
    # Simulate the code's minute-by-minute evaluation:
    # 1. Tier 1: Check minute 1, 2, 3, 4 for move >= $25
    trade_fired = False
    side = ""
    trigger_min = ""
    entry_px = 0.870 # Standard entry ask on $25 move
    exit_desc = ""
    pnl = 0.0
    status = ""
    
    for m_idx in range(1, 5): # Minute 1, 2, 3, 4
        bar = c[m_idx]
        b_open = float(bar[1])
        b_high = float(bar[2])
        b_low  = float(bar[3])
        b_close= float(bar[4])
        
        up_move = b_high - strike
        dn_move = strike - b_low
        
        if up_move >= 25.0:
            trade_fired = True
            side = "UP"
            trigger_min = f"Min {m_idx} (T-{300 - m_idx*60}s)"
            # Simulate exit in subsequent minutes
            # Check if in subsequent bars bid increases (green cashout) or drops (stop loss)
            subsequent_high = max(float(c[k][2]) for k in range(m_idx, 5))
            subsequent_low  = min(float(c[k][3]) for k in range(m_idx, 5))
            final_close     = float(c[4][4])
            
            # If price continued higher by +$15, green cashout triggered
            if (subsequent_high - b_high) >= 15.0:
                exit_desc = f"Green Cashout @ $0.920 (+5¢)"
                pnl = +0.20
                status = "WIN"
            # If price dropped below strike - $10, stop loss bailout fired
            elif (strike - subsequent_low) >= 10.0:
                exit_desc = f"Stop-Loss Bailout @ $0.840"
                pnl = -0.15
                status = "LOSS"
            elif final_close > strike:
                exit_desc = f"Resolution Win @ $1.000"
                pnl = +0.60
                status = "WIN"
            else:
                exit_desc = f"Resolution Loss @ $0.000"
                pnl = -4.00
                status = "LOSS"
            break
            
        elif dn_move >= 25.0:
            trade_fired = True
            side = "DOWN"
            trigger_min = f"Min {m_idx} (T-{300 - m_idx*60}s)"
            subsequent_low  = min(float(c[k][3]) for k in range(m_idx, 5))
            subsequent_high = max(float(c[k][2]) for k in range(m_idx, 5))
            final_close     = float(c[4][4])
            
            if (b_low - subsequent_low) >= 15.0:
                exit_desc = f"Green Cashout @ $0.920 (+5¢)"
                pnl = +0.20
                status = "WIN"
            elif (subsequent_high - strike) >= 10.0:
                exit_desc = f"Stop-Loss Bailout @ $0.840"
                pnl = -0.15
                status = "LOSS"
            elif final_close < strike:
                exit_desc = f"Resolution Win @ $1.000"
                pnl = +0.60
                status = "WIN"
            else:
                exit_desc = f"Resolution Loss @ $0.000"
                pnl = -4.00
                status = "LOSS"
            break
            
    # If no Tier 1 fired, check Tier 2 at T-12s
    if not trade_fired:
        t12_close = float(c[4][4])
        gap = t12_close - strike
        if abs(gap) >= 12.0:
            trade_fired = True
            side = "UP" if gap > 0 else "DOWN"
            trigger_min = "T-12s (Late)"
            entry_px = 0.940
            final_close = float(c[4][4])
            if (side == "UP" and final_close > strike) or (side == "DOWN" and final_close < strike):
                exit_desc = "Resolution Win @ $1.000"
                pnl = +0.25
                status = "WIN"
            else:
                exit_desc = "Resolution Loss @ $0.000"
                pnl = -4.00
                status = "LOSS"
        else:
            trigger_min = "No Trade (Gap < $12)"
            side = "—"
            entry_px = 0.0
            exit_desc = "Skipped (Quiet Candle)"
            pnl = 0.0
            status = "SKIP"
            
    if trade_fired:
        total_sim_trades += 1
        total_sim_profit += pnl
        if status == "WIN":
            total_sim_wins += 1
        else:
            total_sim_losses += 1
            
    # Print sample of markets (first 25, last 25, and all losses)
    if idx <= 20 or idx >= 270 or status == "LOSS":
        print(f"{idx:<3} | {dt_str:<16} | ${strike:<9.2f} | {trigger_min:<12} | {side:<4} | ${entry_px:<8.3f} | {exit_desc:<28} | ${pnl:<+7.2f} | {status}")

print("-" * 115)
print(f"📊 24-HOUR CODE LOGIC TOTALS:")
print(f"  • Total Candles Analyzed: {len(candles_5m)}")
print(f"  • Total Trades Fired:     {total_sim_trades}")
print(f"  • Wins:                   {total_sim_wins} ({(total_sim_wins/total_sim_trades*100):.1f}%)")
print(f"  • Losses:                 {total_sim_losses} ({(total_sim_losses/total_sim_trades*100):.1f}%)")
print(f"  • Net Simulated PnL:      ${total_sim_profit:+.2f}")
print("="*115)
