import json

# Project 50 rounds for each bot before and after remedies
# Baseline parameters: $1.00 fixed stake per round vs compounding sprint stake

bots_analysis = [
    {
        "name": "close_to_market_rollover_bot.py",
        "current_win_rate": 100.0,
        "current_pnl": 0.29,
        "remedy": "Maintain T-12s to T-5s window; cap max price at $0.85.",
        "projected_win_rate": 94.0,
        "avg_buy_price": 0.75,
        "notes": "Optimal risk/reward. Buying @ $0.75 yields +$0.33 profit per win."
    },
    {
        "name": "pure_close_single_stake_bot.py / pure_close_rollover_bot.py",
        "current_win_rate": 87.9,
        "current_pnl": -10.95,
        "remedy": "Add MAX_PRICE_LIMIT = 0.85 and MIN_PRICE_LIMIT = 0.65.",
        "projected_win_rate": 92.0,
        "avg_buy_price": 0.75,
        "notes": "Fixes negative EV losses by cutting out $0.95+ buys."
    },
    {
        "name": "triple_close_scaling_bot.py",
        "current_win_rate": 89.5,
        "current_pnl": -8.55,
        "remedy": "Cap max price at $0.85; enforce $20+ BTC move threshold.",
        "projected_win_rate": 92.0,
        "avg_buy_price": 0.76,
        "notes": "High execution volume with positive expected value."
    },
    {
        "name": "five_mins_hybrid_sprint.py (Current Active Bot)",
        "current_win_rate": 85.4,
        "current_pnl": -11.62,
        "remedy": "Change BET_WINDOW_START from 80s to 12s; cap entry price to $0.65-$0.85.",
        "projected_win_rate": 92.0,
        "avg_buy_price": 0.75,
        "notes": "Eliminates premature T-80s reversal losses."
    },
    {
        "name": "trend_catcher_rollover_bot.py",
        "current_win_rate": 28.6,
        "current_pnl": -3.08,
        "remedy": "Extend execution window from T-15s to T-5s; raise confidence to 0.70.",
        "projected_win_rate": 85.0,
        "avg_buy_price": 0.72,
        "notes": "Currently stops betting too early (T-15s)."
    }
]

# Calculate 50-round projection (Flat $1 stake)
for b in bots_analysis:
    wr = b['projected_win_rate'] / 100.0
    p_buy = b['avg_buy_price']
    
    wins_50 = round(50 * wr)
    losses_50 = 50 - wins_50
    
    # Profit per win = (1 / p_buy) - 1
    profit_per_win = (1.00 / p_buy) - 1.00
    total_win_profit = wins_50 * profit_per_win
    total_loss_cost = losses_50 * 1.00
    
    net_50_flat = total_win_profit - total_loss_cost
    
    b['50_round_flat_stake_pnl'] = round(net_50_flat, 2)
    b['50_round_wins'] = wins_50
    b['50_round_losses'] = losses_50

with open('scratch/50_round_projections.json', 'w') as f:
    json.dump(bots_analysis, f, indent=2)

print("Calculated 50-round projections.")
