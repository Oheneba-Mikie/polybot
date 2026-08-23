import os
import sys
import json
import time
import datetime
import requests
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST = "https://data-api.polymarket.com"

print("="*100)
print("🚀 6-HOUR POLYMARKET AUDIT: BUYING AT 0.97 AND SELLING AT 0.98 / 0.99 SCALPING BACKTEST")
print("="*100)

now = time.time()
current_w_s = int(now // 300) * 300

# 6 hours = 72 five-minute candles
num_candles = 72
candle_timestamps = [current_w_s - (i * 300) for i in range(num_candles)]
candle_timestamps.reverse()

print(f"Auditing {len(candle_timestamps)} consecutive 5-minute candles across the past 6 hours...\n")

trades_by_candle = []

for idx, ts in enumerate(candle_timestamps):
    slug = f"btc-updown-5m-{ts}"
    dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%H:%M UTC")
    
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()
        if not r or not r[0].get("markets"):
            continue
        mkt = r[0]["markets"][0]
        cid = mkt.get("conditionId")
        title = mkt.get("question", slug)
        
        # Get outcome prices/winner
        pxs = json.loads(mkt.get("outcomePrices") or "[]")
        winner = "OPEN"
        if pxs:
            if float(pxs[0]) >= 0.99: winner = "UP"
            elif float(pxs[1]) >= 0.99: winner = "DOWN"

        # Fetch trades
        r_t = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=500", timeout=5).json()
        trades = r_t if r_t else []
        
        if trades:
            # Sort trades strictly by timestamp
            sorted_trades = sorted(trades, key=lambda x: x.get("timestamp", 0))
            trades_by_candle.append({
                "candle": dt_str,
                "ts": ts,
                "slug": slug,
                "winner": winner,
                "trades": sorted_trades
            })
    except Exception as e:
        continue

print(f"Successfully loaded trade history for {len(trades_by_candle)} 5-minute candles.\n")

# Backtest Simulation
# Rules:
# Entry: When a token touches 0.97 (or 0.96-0.97) for the first time in the candle
# Exit Target: Sell at 0.98 or 0.99 as soon as a trade occurs at >= target price
# Bailout / Expiration: If it never reaches target before candle ends, sell at final market price or settlement

def run_scalp_sim(entry_price=0.97, target_price=0.98, starting_balance=5.0, rollover=True):
    balance = starting_balance
    total_trades = 0
    wins = 0
    losses = 0
    trade_logs = []
    
    for c in trades_by_candle:
        trades = c["trades"]
        winner = c["winner"]
        
        # Separate trades into UP and DOWN streams in chronological order
        up_trades = [(t.get("timestamp", 0), float(t.get("price", 0)), float(t.get("size", 0))) for t in trades if str(t.get("outcome")).lower() in ("up", "yes")]
        dn_trades = [(t.get("timestamp", 0), float(t.get("price", 0)), float(t.get("size", 0))) for t in trades if str(t.get("outcome")).lower() in ("down", "no")]
        
        # Check for 0.97 entry on either side
        for side_name, side_trades in [("UP", up_trades), ("DOWN", dn_trades)]:
            entered = False
            entry_ts = None
            exit_ts = None
            exit_px = None
            status = None
            
            for i, (ts, px, sz) in enumerate(side_trades):
                if not entered:
                    if px >= entry_price and px < 0.985: # Entry trigger at ~0.97
                        entered = True
                        entry_ts = ts
                else:
                    # Look for exit at target_price (0.98 or 0.99)
                    if px >= target_price:
                        exit_ts = ts
                        exit_px = px
                        status = "WIN_SCALP"
                        break
            
            if entered:
                total_trades += 1
                stake = balance if rollover else starting_balance
                shares = stake / entry_price
                
                if status == "WIN_SCALP":
                    wins += 1
                    hold_time_s = exit_ts - entry_ts if exit_ts and entry_ts else 0
                    pnl = shares * (exit_px - entry_price)
                    new_balance = balance + pnl
                    trade_logs.append({
                        "candle": c["candle"],
                        "side": side_name,
                        "entry_px": entry_price,
                        "exit_px": exit_px,
                        "hold_time_s": hold_time_s,
                        "status": "WIN",
                        "pnl": round(pnl, 4),
                        "prev_balance": round(balance, 2),
                        "new_balance": round(new_balance, 2)
                    })
                    balance = new_balance
                else:
                    # Never reached target before candle ended
                    losses += 1
                    # Did it win at settlement or lose?
                    final_settle = 1.00 if winner == side_name else 0.00
                    pnl = shares * (final_settle - entry_price)
                    new_balance = max(0.0, balance + pnl)
                    trade_logs.append({
                        "candle": c["candle"],
                        "side": side_name,
                        "entry_px": entry_price,
                        "exit_px": final_settle,
                        "hold_time_s": 300,
                        "status": "SETTLE_WIN" if final_settle == 1.00 else "LOSS",
                        "pnl": round(pnl, 4),
                        "prev_balance": round(balance, 2),
                        "new_balance": round(new_balance, 2)
                    })
                    balance = new_balance
                
                break # Max 1 trade per candle
                
    return {
        "final_balance": round(balance, 2),
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": round((wins / total_trades * 100), 1) if total_trades > 0 else 0,
        "logs": trade_logs
    }

# Run 2 key variations:
# 1. Buy @ 0.97 -> Sell @ 0.98 (Quick 1¢ Scalp)
# 2. Buy @ 0.97 -> Sell @ 0.99 (2¢ Scalp)
sim_98 = run_scalp_sim(entry_price=0.97, target_price=0.98, starting_balance=5.0, rollover=True)
sim_99 = run_scalp_sim(entry_price=0.97, target_price=0.99, starting_balance=5.0, rollover=True)
sim_fixed_98 = run_scalp_sim(entry_price=0.97, target_price=0.98, starting_balance=5.0, rollover=False)

print("="*100)
print(f"📊 BACKTEST RESULTS: $5.00 STARTING BALANCE ACROSS PAST 6 HOURS")
print("="*100)
print(f"STRATEGY 1: Buy @ 0.97  -->  Sell @ 0.98 (Full Rollover Compounding)")
print(f"  • Total Trades Triggered : {sim_98['total_trades']}")
print(f"  • Successful Scalps Sold : {sim_98['wins']} wins")
print(f"  • Failed Scalps (Unsold) : {sim_98['losses']} losses")
print(f"  • Scalp Win Rate         : {sim_98['win_rate']}%")
print(f"  • Final Wallet Balance   : ${sim_98['final_balance']:.2f} (from $5.00 start)")
print("-"*100)
print(f"STRATEGY 2: Buy @ 0.97  -->  Sell @ 0.99 (Full Rollover Compounding)")
print(f"  • Total Trades Triggered : {sim_99['total_trades']}")
print(f"  • Successful Scalps Sold : {sim_99['wins']} wins")
print(f"  • Failed Scalps (Unsold) : {sim_99['losses']} losses")
print(f"  • Scalp Win Rate         : {sim_99['win_rate']}%")
print(f"  • Final Wallet Balance   : ${sim_99['final_balance']:.2f} (from $5.00 start)")
print("="*100)

print("\n--- SAMPLE CHRONOLOGICAL SCALP TRADES (BUY 0.97 -> SELL 0.98) ---")
print(f"{'CANDLE (UTC)':<14} | {'SIDE':<5} | {'ENTRY':<6} | {'EXIT':<6} | {'HOLD TIME':<10} | {'STATUS':<10} | {'PROFIT':<10} | {'BALANCE ($)'}")
print("-"*100)
for t in sim_98["logs"][:15]:
    hold_str = f"{t['hold_time_s']}s"
    print(f"{t['candle']:<14} | {t['side']:<5} | ${t['entry_px']:.2f} | ${t['exit_px']:.2f} | {hold_str:<10} | {t['status']:<10} | ${t['pnl']:<+9.4f} | ${t['new_balance']:.2f}")

with open("scratch/scalper_6h_simulation.json", "w") as fp:
    json.dump({
        "sim_98_rollover": sim_98,
        "sim_99_rollover": sim_99,
        "sim_98_fixed": sim_fixed_98
    }, fp, indent=2)
