import requests
import json
import time
import datetime
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

# The 3 reversal candles identified:
# 1. 07:25 UTC BTC
# 2. 07:25 UTC ETH
# 3. 08:25 UTC ETH

reversal_cases = [
    ("BTC", "btc-updown-5m-1789629900", "07:25 UTC"),
    ("ETH", "eth-updown-5m-1789629900", "07:25 UTC"),
    ("ETH", "eth-updown-5m-1789633500", "08:25 UTC"),
]

print("=" * 90)
print("DEEP FORENSIC AUDIT: DID THE REVERSALS HAVE A 'HUGE WAVE' OR WERE THEY BLIPS?")
print("=" * 90)

for coin, slug, time_label in reversal_cases:
    print(f"\n" + "-" * 90)
    print(f"🔍 CASE: {coin} 5M @ {time_label} ({slug})")
    print("-" * 90)

    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()
        if not r or not r[0].get("markets"):
            print("Market not found on Gamma")
            continue
        m = r[0]["markets"][0]
        cid = m.get("conditionId")
        outcomes = json.loads(m.get("outcomes") or "[]")
        out_prices = json.loads(m.get("outcomePrices") or "[]")
        p0, p1 = float(out_prices[0]), float(out_prices[1])
        winner = outcomes[0] if p0 > p1 else outcomes[1]
        loser = outcomes[1] if winner == outcomes[0] else outcomes[0]

        print(f"Question: {m.get('question')}")
        print(f"Final Resolution: WINNER = {winner} ($1.00) | LOSER = {loser} ($0.00)")

        # Fetch all trades
        trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=3000", timeout=5).json()
        if not isinstance(trades, list):
            print("No trade data returned")
            continue

        w_ts = int(slug.split("-")[-1])
        parsed = []
        for t in trades:
            tr_ts = t.get("timestamp") or t.get("matchTime")
            if isinstance(tr_ts, str):
                try:
                    tr_ts = datetime.datetime.fromisoformat(tr_ts.replace("Z", "+00:00")).timestamp() if "T" in tr_ts else float(tr_ts)
                except:
                    tr_ts = 0
            if tr_ts and tr_ts > 1e11:
                tr_ts /= 1000.0

            sec = int(tr_ts - w_ts)
            parsed.append({
                "ts": tr_ts,
                "sec": sec,
                "time_str": datetime.datetime.utcfromtimestamp(tr_ts).strftime("%H:%M:%S"),
                "outcome": str(t.get("outcome", "")).upper(),
                "price": float(t.get("price", 0)),
                "size": float(t.get("size", 0)),
                "side": str(t.get("side", "")).upper()
            })

        parsed.sort(key=lambda x: x["ts"])
        total_vol = sum(t["size"] for t in parsed)
        print(f"Total Trades in 5m Window: {len(parsed)} trades | Total Volume: {total_vol:,.0f} shares")

        # Track which token hit >= 0.90, >= 0.95, >= 0.98
        high_trades = [t for t in parsed if t["price"] >= 0.90]
        tokens_hit_90 = set(t["outcome"] for t in high_trades)
        
        # Analyze the trajectory
        print("\n📈 Price Progression Timeline (Every 30s):")
        for bucket in range(0, 310, 30):
            bucket_trades = [t for t in parsed if bucket <= t["sec"] < bucket + 30]
            if bucket_trades:
                # Get max price for each outcome in this 30s bucket
                up_trades = [t for t in bucket_trades if t["outcome"] == outcomes[0].upper()]
                dn_trades = [t for t in bucket_trades if t["outcome"] == outcomes[1].upper()]
                up_p = f"${up_trades[-1]['price']:.2f} ({sum(t['size'] for t in up_trades):,.0f}sh)" if up_trades else "No trade"
                dn_p = f"${dn_trades[-1]['price']:.2f} ({sum(t['size'] for t in dn_trades):,.0f}sh)" if dn_trades else "No trade"
                print(f"  T+{bucket:03d}s to T+{bucket+30:03d}s: {outcomes[0]}: {up_p:<22} | {outcomes[1]}: {dn_p:<22}")

        # Specifically look at the trades at >= 0.98
        t_98 = [t for t in parsed if t["price"] >= 0.975]
        fake_token = t_98[0]["outcome"] if t_98 else None
        vol_at_98 = sum(t["size"] for t in t_98)
        print(f"\n⚠️ The 'Wave' That Hit 0.98:")
        print(f"  Token that hit >= $0.98: {fake_token}")
        print(f"  Did that token WIN? {'NO! It crashed to $0.00' if fake_token != winner.upper() else 'YES'}")
        print(f"  First hit 0.98 at: {t_98[0]['time_str']} (T+{t_98[0]['sec']}s)")
        print(f"  Total trades at >= $0.975: {len(t_98)} trades")
        print(f"  Total shares traded at >= $0.975: {vol_at_98:,.0f} shares")
        print(f"  Sample trades at 0.98:")
        for t in t_98[:5]:
            print(f"    • [{t['time_str']}] {t['side']} {t['size']:,.1f} sh @ ${t['price']:.3f} on {t['outcome']}")

        # Look at the REVERSAL moment: when did the true winner surge from <0.10 to $1.00?
        winner_trades = [t for t in parsed if t["outcome"] == winner.upper()]
        reversal_trades = [t for t in winner_trades if t["sec"] >= t_98[0]["sec"]]
        if reversal_trades:
            print(f"\n💥 The Reversal Moment:")
            print(f"  Winner ({winner}) price when fake token was 0.98: ${reversal_trades[0]['price']:.3f}")
            first_surge = [t for t in reversal_trades if t["price"] >= 0.50]
            if first_surge:
                print(f"  Winner crossed $0.50 at: {first_surge[0]['time_str']} (T+{first_surge[0]['sec']}s, only {300 - first_surge[0]['sec']}s before expiry!)")
            print(f"  Last 5 trades of candle:")
            for t in parsed[-5:]:
                print(f"    • [{t['time_str']} / T+{t['sec']}s] {t['outcome']} @ ${t['price']:.2f} ({t['size']:,.0f} sh)")

    except Exception as e:
        print(f"Error auditing {slug}: {e}")
