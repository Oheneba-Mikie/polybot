import json

# 24 Hours = 288 five-minute candles
TOTAL_CANDLES_24H = 288
QUALIFYING_RATE = 0.4444 # 44.4% of candles had >=100 shares sub-$1.00 crosses
TOTAL_TRADES_24H = int(TOTAL_CANDLES_24H * QUALIFYING_RATE) # 128 trades

AVG_COMBINED_COST = 0.9735 # 97.35 cents avg
RETURN_PER_TRADE = (1.00 - AVG_COMBINED_COST) / AVG_COMBINED_COST # +2.722% per trade

START_CAPITAL = 5.00

# Full compounding
final_balance = START_CAPITAL * ((1 + RETURN_PER_TRADE) ** TOTAL_TRADES_24H)
total_profit = final_balance - START_CAPITAL
growth_pct = (total_profit / START_CAPITAL) * 100
multiplier = final_balance / START_CAPITAL

print("="*75)
print("     24-HOUR COMPOUNDED ROLLOVER SIMULATION (STARTING WITH $5.00)")
print("="*75)
print(f"Total 5-Minute Candles:         {TOTAL_CANDLES_24H} windows (24 Hours)")
print(f"Qualifying Cross Trades:        {TOTAL_TRADES_24H} trades (1 trade / window >= 100 shares)")
print(f"Average Profit per Trade:       +{RETURN_PER_TRADE*100:.3f}% (Risk-Free $1.00 Payout)")
print(f"Initial Starting Capital:       ${START_CAPITAL:.2f} USDC")
print(f"24-Hour Growth Multiplier:      {multiplier:.2f}x")
print(f"Final 24-Hour Account Balance:  ${final_balance:.2f} USDC")
print(f"Total Net Profit Earned:        +${total_profit:.2f} USDC (+{growth_pct:.1f}%)")
print("="*75)

# Progression breakdown by 4-hour intervals
print("\n--- 24-HOUR HOURLY GROWTH PROGRESSION ---")
print(f"{'Time Elapsed':<15} | {'Trades Executed':<16} | {'Account Balance':<18} | {'Net Profit':<15} | {'Growth'}")
print("-" * 75)

for hr in [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24]:
    trades = int(hr * (TOTAL_TRADES_24H / 24))
    bal = START_CAPITAL * ((1 + RETURN_PER_TRADE) ** trades)
    pnl = bal - START_CAPITAL
    pct = (pnl / START_CAPITAL) * 100
    print(f"Hour {hr:02d}:00        | {trades:3d} trades        | ${bal:8.2f} USDC      | +${pnl:7.2f} USDC  | +{pct:6.1f}%")

print("="*75)
