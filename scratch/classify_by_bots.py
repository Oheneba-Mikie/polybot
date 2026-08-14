import json

with open('scratch/analyzed_trades.json', encoding='utf-8') as f:
    trades = json.load(f)

print(f"Loaded {len(trades)} trades from API.")

bots = {
    "Hybrid Sprint Bot (Early/Mid All-Rules: T-80s to T-35s)": {"wins": 0, "losses": 0, "unresolved": 0, "trades": [], "stake_spent": 0.0, "pnl": 0.0},
    "Close-Only Bot (Late Entries: T-12s to T-2s, $0.65-$0.89)": {"wins": 0, "losses": 0, "unresolved": 0, "trades": [], "stake_spent": 0.0, "pnl": 0.0},
    "Scalper / Extremes Execution ($0.90 - $0.99)": {"wins": 0, "losses": 0, "unresolved": 0, "trades": [], "stake_spent": 0.0, "pnl": 0.0},
    "Long-Shot / Distressed Orders ($0.01 - $0.35)": {"wins": 0, "losses": 0, "unresolved": 0, "trades": [], "stake_spent": 0.0, "pnl": 0.0},
}

for t in trades:
    price = t.get('price', 0)
    size = t.get('usdc_size', 0)
    is_win = t.get('is_win')
    ts = t.get('timestamp', 0)
    sec_in_win = ts % 300
    rem_sec = 300 - sec_in_win

    bot_key = "Hybrid Sprint Bot (Early/Mid All-Rules: T-80s to T-35s)"
    
    if price >= 0.90:
        bot_key = "Scalper / Extremes Execution ($0.90 - $0.99)"
    elif price <= 0.35:
        bot_key = "Long-Shot / Distressed Orders ($0.01 - $0.35)"
    elif rem_sec <= 25 and (0.60 <= price <= 0.89):
        bot_key = "Close-Only Bot (Late Entries: T-12s to T-2s, $0.65-$0.89)"
    else:
        bot_key = "Hybrid Sprint Bot (Early/Mid All-Rules: T-80s to T-35s)"

    b = bots[bot_key]
    b['trades'].append(t)
    b['stake_spent'] += size

    if is_win is True:
        b['wins'] += 1
        payout = size / price if price > 0 else size
        b['pnl'] += (payout - size)
    elif is_win is False:
        b['losses'] += 1
        b['pnl'] -= size
    else:
        b['unresolved'] += 1

print("\n" + "="*95)
print("  BOT CLASSIFICATION & WIN RATE REPORT")
print("="*95)

summary_output = {}

for name, b in bots.items():
    total = b['wins'] + b['losses']
    win_rate = (b['wins'] / total * 100) if total > 0 else 0.0
    print(f"\n[BOT CATEGORY] {name.upper()}")
    print(f"   - Total Trades      : {len(b['trades'])} (Settled: {total}, Unresolved: {b['unresolved']})")
    print(f"   - Wins / Losses     : {b['wins']} W / {b['losses']} L")
    print(f"   - WIN RATE          : {win_rate:.1f}%")
    print(f"   - Total Volume Spent: ${b['stake_spent']:.2f}")
    print(f"   - Estimated Net P&L : ${b['pnl']:+.2f}")
    
    summary_output[name] = {
        "total_trades": len(b['trades']),
        "wins": b['wins'],
        "losses": b['losses'],
        "win_rate_pct": round(win_rate, 1),
        "stake_spent_usd": round(b['stake_spent'], 2),
        "pnl_usd": round(b['pnl'], 2)
    }

with open('scratch/bot_summary.json', 'w', encoding='utf-8') as f:
    json.dump(summary_output, f, indent=2)
