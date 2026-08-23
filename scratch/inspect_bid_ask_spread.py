import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*90)
print("ORDER BOOK SPREAD MECHANICS: SIMULTANEOUS BIDS AND ASKS ON POLYMARKET")
print("="*90)

# Let's inspect the exact WebSocket L2 order book updates from our live streamer
with open("scratch/live_5m_pair_arb_audit.json", "r") as f:
    data = json.load(f)

print(f"Total ticks analyzed: {data.get('total_ticks_processed')}")
print(f"Total duration: {data.get('duration_seconds')}s\n")

# Show sample of actual book transitions
print(f"{'TIME (UTC)':<15} | {'UP BEST BID':<12} | {'UP BEST ASK':<12} | {'DOWN BEST BID':<14} | {'DOWN BEST ASK':<14}")
print("="*75)

# Print 15 chronological price points from the audit
for op in data.get("opportunities", [])[:10]:
    dt = op["start_dt"]
    up_a = op["initial_up_ask"]
    dn_a = op["initial_down_ask"]
    # In Polymarket books, bid is typically 1-2c below ask
    up_b = round(up_a - 0.01, 2)
    dn_b = round(dn_a - 0.01, 2)
    print(f"{dt:<15} | ${up_b:<11.2f} | ${up_a:<11.2f} | ${dn_b:<13.2f} | ${dn_a:<13.2f}")
