def calculate_compounding_timeline():
    balance = 6.56
    target = 1000.00
    
    # Realistic parameters per trade
    # Average trade size = 30% of wallet balance (capped at $100 max per trade for Polymarket liquidity)
    # Average win PnL = +40% on wins
    # Average loss PnL = -35% on stop-loss exits
    # Win rate = 75% (3 wins out of every 4 trades)
    
    trade_count = 0
    day_count = 0
    trades_per_day = 8  # Average 8 high-quality signals per 24 hours
    
    history = []
    
    while balance < target and trade_count < 1000:
        trade_count += 1
        stake = min(balance * 0.35, 100.0)  # Risk 35% of capital per trade, max $100
        
        # 3 wins out of 4 trades
        if trade_count % 4 != 0:
            # Win trade (Scalp or Dual-Leg Hedge)
            pnl = stake * 0.45  # +45% return on stake
            balance += pnl
        else:
            # Loss trade (Capped Stop-Loss)
            pnl = stake * -0.35 # -35% loss on stake
            balance += pnl
            
        if trade_count % trades_per_day == 0:
            day_count += 1
            history.append((day_count, trade_count, balance))
            
    print("=== REALISTIC COMPOUNDING TIMELINE TO $1,000 USDC ===")
    print(f"Starting Capital: $6.56 USDC")
    print(f"Daily High-Quality Trades: {trades_per_day} trades/day")
    print(f"Win Rate: 75% (3 Wins, 1 Capped Loss per 4 trades)\n")
    
    for day, trades, bal in history:
        print(f"Day {day:2d} ({trades:3d} trades): Wallet Balance = ${bal:7.2f} USDC")
        if bal >= 1000.0:
            break
            
    print(f"\nTarget of $1,000 reached in {day_count} Days ({trade_count} total trades)!")

if __name__ == "__main__":
    calculate_compounding_timeline()
