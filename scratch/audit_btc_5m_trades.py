import requests
import json
import time

now_ts = time.time()
btc_trades = []

for offset in range(0, 15):
    w_start = int((now_ts - offset*300) // 300) * 300
    slug = f"btc-updown-5m-{w_start}"
    try:
        r = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=5).json()
        if not r or "markets" not in r[0]: continue
        cid = r[0]["markets"][0]["conditionId"]
        
        r_tr = requests.get(f"https://data-api.polymarket.com/trades?condition_id={cid}&limit=100", timeout=5).json()
        if isinstance(r_tr, list):
            for tr in r_tr:
                outcome = str(tr.get("outcome", "")).upper()
                if outcome in ("UP", "DOWN"):
                    btc_trades.append({
                        "cycle": slug,
                        "time": time.strftime("%H:%M:%S", time.gmtime(tr.get("timestamp", 0))),
                        "side": tr.get("side"),
                        "outcome": outcome,
                        "price": float(tr.get("price", 0)),
                        "size": float(tr.get("size", 0)),
                        "val": float(tr.get("price", 0)) * float(tr.get("size", 0))
                    })
    except Exception as e:
        pass

print("="*80)
print(f"AUDITED {len(btc_trades)} REAL BTC 5-MINUTE TRADES IN THE PAST 75 MINUTES")
print("="*80)

p98_trades = [t for t in btc_trades if 0.97 <= t["price"] <= 0.985]
p99_trades = [t for t in btc_trades if t["price"] >= 0.99]

print(f"Trades at $0.97 - $0.98: {len(p98_trades)} trades (Total: {sum(t['val'] for t in p98_trades):,.2f} USDC)")
print(f"Trades at $0.99:        {len(p99_trades)} trades (Total: {sum(t['val'] for t in p99_trades):,.2f} USDC)")

print("\n--- SAMPLE REAL 0.98 & 0.99 TRADES ON POLYMARKET ---")
for t in (p98_trades + p99_trades)[:20]:
    print(f"[{t['time']} UTC] {t['cycle']} | {t['side']} {t['outcome']} @ ${t['price']:.2f} | Size: {t['size']:,.1f} shares (${t['val']:,.2f} USDC)")
print("="*80)
