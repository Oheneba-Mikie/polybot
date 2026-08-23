import json

with open('scratch/daily_breakdown.json') as f:
    daily = json.load(f)

for day in ['2026-08-19', '2026-08-20', '2026-08-21']:
    if day not in daily:
        continue
    data = daily[day]
    print("="*120)
    print(f"DAY: {day} | Spent: ${data['spent']:.2f} | Received: ${data['received']:.2f} | PnL: ${data['pnl']:+.2f} | Wins: {data['wins']} | Losses: {data['losses']}")
    print("="*120)
    for idx, t in enumerate(data['details'], 1):
        print(f"\n#{idx} [{t['dt']}] Status: {t['status']:<4} | Spent: ${t['spent']:6.2f} | Recv: ${t['recv']:6.2f} | PnL: {t['pnl']:+6.2f}")
        print(f"   Market: {t['title']}")
        print(f"   Buys:")
        for b in t['buys']:
            print(f"      Outcome: {b['outcome']:<5} | Px: {b['price']:.3f} | Shares: {b['shares']:6.2f} | Cost: ${b['size']:.2f}")
        if t['sells']:
            print(f"   Sells:")
            for s in t['sells']:
                print(f"      Outcome: {s['outcome']:<5} | Px: {s['price']:.3f} | Shares: {s['shares']:6.2f} | Proceeds: ${s['size']:.2f}")
        if t['redeems']:
            print(f"   Redeems:")
            for r in t['redeems']:
                print(f"      Outcome: {r['outcome']:<5} | Shares: {r['shares']:6.2f} | Payout: ${r['size']:.2f}")
        else:
            if t['status'] == 'LOSS':
                print(f"   >>> NO REDEEMS (TOTAL LOSS OR EXPIRED/UNREDEEMED)")
