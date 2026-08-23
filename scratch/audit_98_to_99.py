import requests
import json
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

print("="*95)
print("🔍 TESTING 98¢ -> 99¢ vs 97¢ -> 99¢ vs 97¢ -> 98¢ ACROSS LAST 30 CANDLES:")
print("="*95)

now = time.time()
cur_w_s = int(now // 300) * 300
candles_ts = [cur_w_s - (i * 300) for i in range(1, 31)]
candles_ts.reverse()

# Track stats for all 3 strategies
stats = {
    "97_to_98": {"wins": 0, "bailouts": 0, "balance": 5.45, "triggers": 0},
    "98_to_99": {"wins": 0, "bailouts": 0, "balance": 5.45, "triggers": 0},
    "97_to_99": {"wins": 0, "bailouts": 0, "balance": 5.45, "triggers": 0}
}

for ts in candles_ts:
    slug = f"btc-updown-5m-{ts}"
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()
        if not r or not r[0].get("markets"): continue
        mkt = r[0]["markets"][0]
        cid = mkt.get("conditionId")
        
        r_trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=500", timeout=5).json()
        if not r_trades: continue
        trades = sorted(r_trades, key=lambda x: x.get("timestamp", 0))
        
        # 1. Test 97 -> 98
        entered_97 = False
        side_97 = None
        t_97 = None
        for t in trades:
            px = float(t.get("price", 0))
            ts_sec = t.get("timestamp", 0)
            if not entered_97 and 0.965 <= px <= 0.975:
                entered_97 = True
                side_97 = t.get("outcome", "")
                t_97 = ts_sec
            elif entered_97 and ts_sec > t_97:
                if t.get("outcome") == side_97 and px >= 0.980:
                    stats["97_to_98"]["wins"] += 1
                    stats["97_to_98"]["balance"] = round(stats["97_to_98"]["balance"] * 1.0103, 2)
                    break
                elif (ts_sec - t_97) > 40.0:
                    stats["97_to_98"]["bailouts"] += 1
                    stats["97_to_98"]["balance"] = round(stats["97_to_98"]["balance"] * 0.99, 2)
                    break
        if entered_97: stats["97_to_98"]["triggers"] += 1

        # 2. Test 98 -> 99
        entered_98 = False
        side_98 = None
        t_98 = None
        for t in trades:
            px = float(t.get("price", 0))
            ts_sec = t.get("timestamp", 0)
            if not entered_98 and 0.978 <= px <= 0.985:
                entered_98 = True
                side_98 = t.get("outcome", "")
                t_98 = ts_sec
            elif entered_98 and ts_sec > t_98:
                if t.get("outcome") == side_98 and px >= 0.990:
                    stats["98_to_99"]["wins"] += 1
                    stats["98_to_99"]["balance"] = round(stats["98_to_99"]["balance"] * 1.0102, 2)
                    break
                elif (ts_sec - t_98) > 40.0:
                    stats["98_to_99"]["bailouts"] += 1
                    stats["98_to_99"]["balance"] = round(stats["98_to_99"]["balance"] * 0.98, 2)
                    break
        if entered_98: stats["98_to_99"]["triggers"] += 1

        # 3. Test 97 -> 99 (+2.06% profit!)
        entered_97_99 = False
        side_97_99 = None
        t_97_99 = None
        for t in trades:
            px = float(t.get("price", 0))
            ts_sec = t.get("timestamp", 0)
            if not entered_97_99 and 0.965 <= px <= 0.975:
                entered_97_99 = True
                side_97_99 = t.get("outcome", "")
                t_97_99 = ts_sec
            elif entered_97_99 and ts_sec > t_97_99:
                if t.get("outcome") == side_97_99 and px >= 0.990:
                    stats["97_to_99"]["wins"] += 1
                    stats["97_to_99"]["balance"] = round(stats["97_to_99"]["balance"] * 1.0206, 2)
                    break
                elif (ts_sec - t_97_99) > 40.0:
                    stats["97_to_99"]["bailouts"] += 1
                    stats["97_to_99"]["balance"] = round(stats["97_to_99"]["balance"] * 0.99, 2)
                    break
        if entered_97_99: stats["97_to_99"]["triggers"] += 1

    except Exception:
        continue

print(f"{'Strategy':<20} | {'Triggers':<10} | {'Wins':<10} | {'Win Rate':<10} | {'Bailouts':<10} | {'Final Balance'}")
print("-" * 80)
for strat, d in stats.items():
    wr = d["wins"] / max(1, d["triggers"]) * 100
    print(f"{strat:<20} | {d['triggers']:<10} | {d['wins']:<10} | {wr:.1f}%     | {d['bailouts']:<10} | ${d['balance']:.2f} (+{(d['balance']-5.45)/5.45*100:.1f}%)")
print("="*95)
