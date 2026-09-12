import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*105)
print("🔍 COMPREHENSIVE FORENSIC AUDIT: WHY DID OUR BOT LOSE ON LIVE MARKETS?")
print("="*105)

addr = "0x81ad69942a32f7b1df4d16f0c3f79311f55de50a"

# Fetch all trades
r_trades = requests.get(f"https://data-api.polymarket.com/trades?user={addr}&limit=50").json()
r_activity = requests.get(f"https://data-api.polymarket.com/activity?user={addr}&limit=50").json()

print(f"Total Trades Recorded: {len(r_trades)}")

# Group trades by market slug / candle
markets = {}
for t in r_trades:
    title = t.get("title", "Unknown")
    if title not in markets:
        markets[title] = []
    markets[title].append(t)

print(f"Total 5-Minute Markets Traded: {len(markets)}\n")

for title, m_trades in markets.items():
    print("-" * 105)
    print(f"🎯 Market: {title}")
    
    # Sort trades chronologically
    sorted_t = sorted(m_trades, key=lambda x: x.get("timestamp", 0))
    
    total_bought_usdc = 0.0
    total_sold_usdc = 0.0
    shares_bought = 0.0
    shares_sold = 0.0
    side_traded = ""
    
    for t in sorted_t:
        side = t.get("side")
        sz = float(t.get("size", 0))
        px = float(t.get("price", 0))
        val = sz * px
        outcome = t.get("outcome")
        ts = t.get("timestamp", 0)
        dt = time.strftime("%H:%M:%S UTC", time.gmtime(ts))
        
        # Calculate second in 5-minute candle
        candle_sec = ts % 300
        min_sec = f"{candle_sec // 60}m {candle_sec % 60:02d}s"
        time_remaining = 300 - candle_sec
        
        side_traded = outcome
        if side == "BUY":
            total_bought_usdc += val
            shares_bought += sz
            print(f"  • [{dt}] BUY  {sz:.2f} sh of {outcome:<4} @ ${px:.3f} (${val:.2f}) | Candle Time: {min_sec} (T-{time_remaining}s left)")
        else:
            total_sold_usdc += val
            shares_sold += sz
            print(f"  • [{dt}] SELL {sz:.2f} sh of {outcome:<4} @ ${px:.3f} (${val:.2f}) | Candle Time: {min_sec} (T-{time_remaining}s left)")
            
    # Check if there was a redemption
    redemptions = [a for a in r_activity if a.get("title") == title and a.get("type") == "REDEEM"]
    redeemed_val = sum(float(a.get("usdcSize", a.get("size", 0))) for a in redemptions)
    if redeemed_val > 0:
        print(f"  • 🎉 REDEMPTION PAYOUT: +${redeemed_val:.2f} USDC")
        
    net_pnl = (total_sold_usdc + redeemed_val) - total_bought_usdc
    outcome_str = f"PROFIT (+${net_pnl:.2f})" if net_pnl > 0.005 else (f"LOSS (-${abs(net_pnl):.2f})" if net_pnl < -0.005 else "BREAKEVEN ($0.00)")
    
    print(f"  📊 Financial Result: {outcome_str} (Bought: ${total_bought_usdc:.2f}, Recovered: ${total_sold_usdc + redeemed_val:.2f})")
    
    # Forensic Reason Analysis
    first_buy = [t for t in sorted_t if t.get("side") == "BUY"]
    if first_buy:
        fb_ts = first_buy[0].get("timestamp", 0)
        fb_rem = 300 - (fb_ts % 300)
        
        if net_pnl < -0.005:
            print("  🔴 ROOT CAUSE OF LOSS:")
            if fb_rem > 60:
                print(f"     1. Premature Mid-Candle Entry: Bot entered with {fb_rem} seconds remaining (Minute { (300-fb_rem)//60 }).")
                print(f"     2. Price Reversal / Fakeout: Because there was still {fb_rem}s left in the candle, Bitcoin reversed.")
                if total_sold_usdc > 0:
                    print("     3. Stop-Loss Trigger: The code panicked and sold at a lower bid to 'cut loss'.")
                else:
                    print("     3. Expired Worthless: Held a position that reversed early into close.")
        elif net_pnl > 0.005:
            print("  🟢 ROOT CAUSE OF PROFIT:")
            if redeemed_val > 0:
                print("     1. Full Resolution Win: Held winning side into candle expiration for 100% payout ($1.00/sh).")
            else:
                print("     2. Green Micro-Scalp: Sold into higher buyers.")

print("="*105)
