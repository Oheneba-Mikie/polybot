import requests, datetime

print("="*80)
print("🔬 24-HOUR AUDIT: $30 SPOT MOVE vs $40 SPOT MOVE AT 3.5+ MINUTES (T+200s)")
print("="*80)

# Fetch past 288 5m candles
r5 = requests.get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=288").json()

# Fetch 1m candles covering the 24 hours
r1_late = requests.get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=1000").json()
t_first = r1_late[0][0]
r1_early = requests.get(f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=500&endTime={t_first-1}").json()
all_1m = {k[0]: k for k in (r1_early + r1_late)}

# For each 5m candle, check:
# 1. Open price (strike)
# 2. Price at T+200s (~3.33 min, end of minute 3)
# 3. Final close price at T+300s (winner)
# 4. Did $30 wave win? Did $40 wave win? Did any reverse?

stats = {
    "30": {"total": 0, "won": 0, "reversed": 0, "avg_profit": 0.0, "reversals": []},
    "40": {"total": 0, "won": 0, "reversed": 0, "avg_profit": 0.0, "reversals": []}
}

for k in r5:
    t5 = k[0]
    t5_str = datetime.datetime.fromtimestamp(t5/1000, datetime.timezone.utc).strftime("%H:%M")
    open_p = float(k[1])
    close_p = float(k[4])
    candle_winner = "UP" if close_p >= open_p else "DOWN"

    # Price at T+200s (end of minute 3, i.e., 3 mins in)
    k1_m3 = all_1m.get(t5 + 180000)
    if not k1_m3:
        continue
    price_t200 = float(k1_m3[4])
    move_t200 = price_t200 - open_p
    abs_move = abs(move_t200)
    dir_t200 = "UP" if move_t200 >= 0 else "DOWN"

    # Test >= $30
    if abs_move >= 30.0:
        stats["30"]["total"] += 1
        if dir_t200 == candle_winner:
            stats["30"]["won"] += 1
        else:
            stats["30"]["reversed"] += 1
            stats["30"]["reversals"].append({
                "time": t5_str, "move_t200": move_t200, "final_move": close_p - open_p,
                "dir_t200": dir_t200, "winner": candle_winner
            })

    # Test >= $40
    if abs_move >= 40.0:
        stats["40"]["total"] += 1
        if dir_t200 == candle_winner:
            stats["40"]["won"] += 1
        else:
            stats["40"]["reversed"] += 1
            stats["40"]["reversals"].append({
                "time": t5_str, "move_t200": move_t200, "final_move": close_p - open_p,
                "dir_t200": dir_t200, "winner": candle_winner
            })

print(f"\n📊 1. COMPARATIVE RESULTS OVER 288 CANDLES (24 HOURS):")
print(f"{'Metric':<32} | {'$30 Move Threshold':<20} | {'$40 Move Threshold':<20}")
print("-" * 78)
tot_30 = stats["30"]["total"]
tot_40 = stats["40"]["total"]
won_30 = stats["30"]["won"]
won_40 = stats["40"]["won"]
rev_30 = stats["30"]["reversed"]
rev_40 = stats["40"]["reversed"]

wr_30 = (won_30 / tot_30 * 100) if tot_30 else 0
wr_40 = (won_40 / tot_40 * 100) if tot_40 else 0

print(f"{'Total Qualified Candles':<32} | {tot_30:<20} | {tot_40:<20}")
print(f"{'Trades per Hour (Frequency)':<32} | {tot_30/24:<20.1f} | {tot_40/24:<20.1f}")
print(f"{'Successful Waves (Won)':<32} | {won_30:<20} | {won_40:<20}")
print(f"{'Reversals (Lost/Failed)':<32} | {rev_30:<20} | {rev_40:<20}")
print(f"{'WIN RATE':<32} | {wr_30:<19.2f}% | {wr_40:<19.2f}%")

print("\n" + "="*78)
print("📋 2. REVERSAL ANALYSIS:")
if rev_30 > 0:
    print(f"Reversals at $30 threshold ({rev_30}):")
    for r in stats["30"]["reversals"]:
        print(f"  • {r['time']} UTC: At T+200s was {r['dir_t200']} ({r['move_t200']:+.1f}$), ended {r['winner']} ({r['final_move']:+.1f}$)")
else:
    print("Zero reversals at $30 threshold!")

if rev_40 > 0:
    print(f"\nReversals at $40 threshold ({rev_40}):")
    for r in stats["40"]["reversals"]:
        print(f"  • {r['time']} UTC: At T+200s was {r['dir_t200']} ({r['move_t200']:+.1f}$), ended {r['winner']} ({r['final_move']:+.1f}$)")
else:
    print("\nZero reversals at $40 threshold!")

print("="*78)
