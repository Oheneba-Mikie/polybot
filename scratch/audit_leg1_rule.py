import requests, datetime, time

# Fetch 288 5-minute candles (past 24 hours) from Binance BTCUSDT
r = requests.get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=288").json()

print(f"Auditing all {len(r)} 5-minute candles over the past 24 hours...")

# Let's count:
# 1. Total candles with >= $30 move:
#    - at T+60s (minute 1)
#    - at T+120s (minute 2)
#    - at T+180s (minute 3)
#    - at T+200s (3.5 min)
#    - at T+240s (minute 4)

# For detailed analysis, let's pull 1-minute klines for the past 24 hours (1440 1m candles)
r_1m = requests.get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=1000").json()
# Fetch another 500 to cover 1440
first_t = r_1m[0][0]
r_1m_prev = requests.get(f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=500&endTime={first_t-1}").json()
all_1m = r_1m_prev + r_1m

# Map 1m candles by timestamp
m1_map = {k[0]: k for k in all_1m}

# Group into 5-minute candles
results = []
for k5 in r:
    t5_open = k5[0]
    p5_open = float(k5[1])
    
    # 1-minute intervals in this 5m candle:
    # m0: t5_open (T+0s to T+60s)
    # m1: t5_open + 60000 (T+60s to T+120s)
    # m2: t5_open + 120000 (T+120s to T+180s)
    # m3: t5_open + 180000 (T+180s to T+240s)
    # m4: t5_open + 240000 (T+240s to T+300s)
    
    m_moves = []
    for offset in [0, 60000, 120000, 180000, 240000]:
        k1 = m1_map.get(t5_open + offset)
        if k1:
            c1 = float(k1[4])
            m_moves.append(c1 - p5_open)
        else:
            m_moves.append(0.0)
            
    results.append({
        "time": datetime.datetime.fromtimestamp(t5_open/1000, datetime.timezone.utc).strftime("%H:%M"),
        "open": p5_open,
        "m_moves": m_moves, # moves at end of min 1, 2, 3, 4, 5
        "net_move": float(k5[4]) - p5_open
    })

print(f"Total 5M candles analyzed: {len(results)}")

# Now let's calculate:
# If rule is: Check at Minute 3.5 (~T+200s, between min 3 and min 4):
# Move >= $30
# Token price model on Polymarket (empirical):
# For a move M and time remaining T_rem:
# At T_rem = 100s (T+200s):
# Move $30 -> Token is ~$0.88 - $0.90
# Move $40 -> Token is ~$0.92
# Move $60 -> Token is ~$0.96
# Move $80+ -> Token is ~$0.98

# Let's count how many candles had Move >= $30 at each minute!
for minute_idx, label in [(1, "T+120s (2.0 min)"), (2, "T+180s (3.0 min)"), (3, "T+240s (4.0 min)")]:
    count_30 = sum(1 for r in results if len(r["m_moves"]) > minute_idx and abs(r["m_moves"][minute_idx]) >= 30.0)
    count_40 = sum(1 for r in results if len(r["m_moves"]) > minute_idx and abs(r["m_moves"][minute_idx]) >= 40.0)
    count_60 = sum(1 for r in results if len(r["m_moves"]) > minute_idx and abs(r["m_moves"][minute_idx]) >= 60.0)
    print(f"\n--- {label} ---")
    print(f"  Candles with Move >= $30: {count_30} ({count_30/len(results)*100:.1f}%)")
    print(f"  Candles with Move >= $40: {count_40} ({count_40/len(results)*100:.1f}%)")
    print(f"  Candles with Move >= $60: {count_60} ({count_60/len(results)*100:.1f}%)")

# Now let's see: At T+200s (3.5 min), how many candles had Move between $30 and $40 (where Token <= 0.89)?
# If move > $40 at T+200s, token price is typically > 0.89!
sweet_spot = [r for r in results if len(r['m_moves']) > 2 and 30.0 <= abs(r['m_moves'][2]) <= 42.0]
blowout = [r for r in results if len(r['m_moves']) > 2 and abs(r['m_moves'][2]) > 42.0]

print("\n" + "="*70)
print(f"RESULTS AT 3.0-3.5 MINUTES (Past 24h):")
print(f"• Total candles where move was in the $30-$42 'Sweet Spot' (Token <= $0.89): {len(sweet_spot)} candles ({len(sweet_spot)/len(results)*100:.1f}%)")
print(f"• Total candles where move was > $42 'Blowout' (Token shot past $0.89 to $0.94-$0.98): {len(blowout)} candles ({len(blowout)/len(results)*100:.1f}%)")
print(f"• Ratio: Blowouts outnumber Sweet Spot by {len(blowout)/max(1, len(sweet_spot)):.1f}x!")
