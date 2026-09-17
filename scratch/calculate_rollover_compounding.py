import json

# 64 qualifying trades in 12 hours
N_TRADES = 64
AVG_COMBINED_COST = 0.9735 # 97.35 cents avg
RETURN_PER_TRADE = (1.00 - AVG_COMBINED_COST) / AVG_COMBINED_COST # ~2.722% per trade

# Multiplier after 64 consecutive compounded rollovers:
compound_multiplier = (1 + RETURN_PER_TRADE) ** N_TRADES

starting_balances = [10.0, 25.0, 50.0, 100.0, 250.0, 500.0]

print("="*75)
print("       12-HOUR COMPOUNDED ROLLOVER ASSESSMENT (64 TRADES)")
print("="*75)
print(f"Number of Compounded Trades: {N_TRADES} trades (1 trade per qualifying 5m candle)")
print(f"Average Return per Trade:    +{RETURN_PER_TRADE*100:.3f}% (Risk-Free Arbitrage)")
print(f"Total 12-Hour Multiplier:    {compound_multiplier:.2f}x (+{(compound_multiplier - 1)*100:.1f}%)")
print("="*75)

for start in starting_balances:
    final_balance = start * compound_multiplier
    net_profit = final_balance - start
    print(f"\n[Starting Capital: ${start:.2f} USDC]")
    print(f"   * Final Account Balance after 12h: ${final_balance:.2f} USDC")
    print(f"   * Total Net Profit Generated:     +${net_profit:.2f} USDC")
    print(f"   * Net Growth on Initial Deposit:  +{(net_profit/start)*100:.1f}%")

print("="*75)
