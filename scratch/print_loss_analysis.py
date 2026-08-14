import json
import datetime

with open('scratch/analyzed_trades.json') as f:
    trades = json.load(f)

print(f"Total analyzed trades: {len(trades)}")

wins = [t for t in trades if t['is_win'] is True]
losses = [t for t in trades if t['is_win'] is False]
unresolved = [t for t in trades if t['is_win'] is None]

print(f"Wins: {len(wins)} ({len(wins)/len(trades)*100:.1f}%)")
print(f"Losses: {len(losses)} ({len(losses)/len(trades)*100:.1f}%)")
print(f"Unresolved: {len(unresolved)}")

# Let's inspect all losses, sorted by timestamp descending
losses_sorted = sorted(losses, key=lambda x: x['timestamp'], reverse=True)

print("\n" + "="*90)
print(f"  DETAILED LOSS REPORT ({len(losses_sorted)} LOSSES)")
print("="*90)

loss_categories = {
    "late_reversal": [],  # High entry price ($0.70+), but market reversed
    "low_conviction_slop": [], # Bought at cheap price ($0.05 - $0.35)
    "mid_range_flip": [], # Bought at $0.40 - $0.65
}

for i, l in enumerate(losses_sorted, 1):
    price = l['price']
    bought = l['outcome_bought']
    winner = l['winning_outcome']
    dt = l['datetime']
    title = l['title']
    size = l['usdc_size']
    slug = l['slug']

    cat = "mid_range_flip"
    if price >= 0.70:
        cat = "late_reversal"
    elif price <= 0.35:
        cat = "low_conviction_slop"

    loss_categories[cat].append(l)

    print(f"\nLoss #{i}: {dt} | {title}")
    print(f"  - Slug            : {slug}")
    print(f"  - Bought Outcome  : {bought}")
    print(f"  - Winning Outcome : {winner}")
    print(f"  - Entry Price     : ${price:.4f}  (Cost: ${size:.2f})")
    print(f"  - Primary Reason  : {cat.upper()}")

print("\n" + "="*90)
print("  LOSS CATEGORY SUMMARY")
print("="*90)
print(f"1. Late Reversals (Bought at high confidence >= $0.70, but BTC reversed before close): {len(loss_categories['late_reversal'])} losses")
print(f"2. Mid-Range Flips (Bought at $0.40 - $0.69, weak directional edge): {len(loss_categories['mid_range_flip'])} losses")
print(f"3. Low-Price Bargains (Bought at <= $0.35, high risk long-shot entries): {len(loss_categories['low_conviction_slop'])} losses")

# Also analyze recent losses specifically for five_mins_hybrid_sprint (5-min BTC updown markets)
five_min_btc_losses = [l for l in losses_sorted if 'btc-updown-5m' in (l.get('slug') or '') or '5m' in (l.get('slug') or '') or '5-minute' in l.get('title', '').lower() or '5PM' in l.get('title', '') or '5AM' in l.get('title', '')]
print(f"\nTotal 5-Min BTC Specific Losses: {len(five_min_btc_losses)}")
for idx, l in enumerate(five_min_btc_losses[:15], 1):
    print(f"  {idx}. {l['datetime']} | {l['title']} | Bought: {l['outcome_bought']} @ ${l['price']:.4f} | Winner: {l['winning_outcome']}")
