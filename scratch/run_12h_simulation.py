import json, datetime

scenarios = [
    {
        "name": "Standard Sizing (1 trade / window @ 5 shares)",
        "shares_per_trade": 5,
        "trades_count": 64, # 1 per qualifying window
        "avg_profit_per_share": 0.0265, # Sniping best cross in window (avg 97.35c)
        "avg_cost_per_trade": 5 * 0.9735, # ~$4.87 stake
    },
    {
        "name": "Conservative Sizing (1 trade / window @ 25 shares)",
        "shares_per_trade": 25,
        "trades_count": 64,
        "avg_profit_per_share": 0.0265,
        "avg_cost_per_trade": 25 * 0.9735, # ~$24.34 stake
    },
    {
        "name": "Full Rule Sizing (1 trade / window @ 100 shares)",
        "shares_per_trade": 100,
        "trades_count": 64,
        "avg_profit_per_share": 0.0265,
        "avg_cost_per_trade": 100 * 0.9735, # ~$97.35 stake
    },
    {
        "name": "Aggressive Sizing (All 142 cross events @ 100 shares)",
        "shares_per_trade": 100,
        "trades_count": 142,
        "avg_profit_per_share": 0.0245,
        "avg_cost_per_trade": 100 * 0.9755, # ~$97.55 stake
    },
    {
        "name": "Max Liquidity Sweep (Sweeping full depth ~184.5 shares avg)",
        "shares_per_trade": 184.5,
        "trades_count": 142,
        "avg_profit_per_share": 0.0245,
        "avg_cost_per_trade": 184.5 * 0.9755, # ~$180.00 stake
    }
]

print("="*80)
print("     12-HOUR HISTORICAL ASSESSMENT: >= 100 SHARES ARBITRAGE EARNINGS")
print("="*80)
print("Total 5-Minute Windows in 12 Hours: 144 candles")
print("Windows with >= 100 Shares Crosses: 64 windows (44.4%)")
print("Total >= 100 Shares Cross Events: 142 distinct crosses")
print("Average Return per Arb Trade: +2.5% to +2.7% (Risk-Free $1.00 Payout)")
print("="*80)

for s in scenarios:
    tot_profit = s["shares_per_trade"] * s["trades_count"] * s["avg_profit_per_share"]
    roi_pct = (tot_profit / s["avg_cost_per_trade"]) * 100
    print(f"\n[Scenario] {s['name']}")
    print(f"   * Total Trades Executed: {s['trades_count']} trades")
    print(f"   * Shares per Trade: {s['shares_per_trade']} shares")
    print(f"   * Capital Required per Trade: ${s['avg_cost_per_trade']:.2f} USDC")
    print(f"   * Average Profit per Trade: +${s['shares_per_trade'] * s['avg_profit_per_share']:.3f} USDC")
    print(f"   * TOTAL 12-HOUR EARNINGS: +${tot_profit:.2f} USDC")
    print(f"   * 12-Hour Return on Active Capital: +{roi_pct:.1f}%")
print("="*80)
