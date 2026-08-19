import requests
import json
import time

print("="*80)
print("AUDITING POLYMARKET RECENT PUBLIC TRADE TAPE (PAST 1 HOUR)")
print("="*80)

# Fetch recent trades on Polymarket CLOB for active 5m markets
now_ts = time.time()
trades_analyzed = []

for offset in range(0, 12): # past 12 five-minute cycles (1 hour)
    w_start = int((now_ts - offset*300) // 300) * 300
    slug = f"btc-updown-5m-{w_start}"
    try:
        r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=5).json()
        if not r or "markets" not in r[0]: continue
        m = r[0]["markets"][0]
        token_ids = json.loads(m["clobTokenIds"])
        outcomes = json.loads(m["outcomes"])
        
        for i, tid in enumerate(token_ids):
            side_name = outcomes[i]
            # Fetch recent trades from CLOB
            r_trades = requests.get(f"https://clob.polymarket.com/trades?asset_id={tid}", timeout=5).json()
            trade_list = r_trades.get("data", []) or r_trades if isinstance(r_trades, list) else []
            for tr in trade_list:
                p = float(tr.get("price", 0))
                sz = float(tr.get("size", 0))
                t_ts = tr.get("timestamp")
                if p >= 0.95:
                    trades_analyzed.append({
                        "cycle": slug,
                        "side": side_name,
                        "price": p,
                        "size": sz,
                        "value": p * sz,
                        "timestamp": t_ts
                    })
    except Exception as e:
        pass

print(f"Total High-Probability Trades (Price >= $0.95) in past hour: {len(trades_analyzed)}\n")

trades_98 = [t for t in trades_analyzed if t["price"] == 0.98]
trades_99 = [t for t in trades_analyzed if t["price"] >= 0.99]

print(f"Trades executed at $0.98: {len(trades_98)} trades (Total Volume: {sum(t['value'] for t in trades_98):,.2f} USDC)")
print(f"Trades executed at $0.99: {len(trades_99)} trades (Total Volume: {sum(t['value'] for t in trades_99):,.2f} USDC)")

print("\n--- SAMPLE RECENT $0.98 -> $0.99 REAL MARKET TRADES ---")
for tr in trades_analyzed[:15]:
    print(f"Cycle: {tr['cycle']} | Side: {tr['side']} | Price: ${tr['price']:.4f} | Size: {tr['size']:,.1f} shares (${tr['value']:,.2f} USDC)")
print("="*80)
