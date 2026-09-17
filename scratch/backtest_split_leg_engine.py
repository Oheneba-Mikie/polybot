import requests, datetime, time, sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = 'https://gamma-api.polymarket.com'
DATA_HOST  = 'https://data-api.polymarket.com'

print("=" * 65)
print("SPLIT-LEG ASYNCHRONOUS ARBITRAGE SIMULATOR (PAST 20 CANDLES)")
print("Strategy: Buy Leg 1 when <= $0.45. Hunt for Leg 2 at <= (0.99 - Leg1).")
print("=" * 65)

now = int(time.time())
cur_w_s = (now // 300) * 300
windows = [cur_w_s - (i * 300) for i in range(1, 21)] # Past 20 completed candles
windows.reverse()

total_candles = 0
pairs_completed = 0
single_leg_wins = 0
single_leg_losses = 0
total_pnl = 0.0

completed_pairs = []

for w_s in windows:
    slug = f"eth-updown-5m-{w_s}"
    try:
        r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4).json()
        if not r_evt or not r_evt[0].get("markets"):
            continue
        m = r_evt[0]["markets"][0]
        cid = m.get("conditionId")
        trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=2000", timeout=4).json()
        if not isinstance(trades, list) or len(trades) < 10:
            continue
            
        parsed = []
        for t in trades:
            tr_ts = t.get("timestamp") or t.get("matchTime")
            if isinstance(tr_ts, str):
                try: tr_ts = datetime.datetime.fromisoformat(tr_ts.replace("Z", "+00:00")).timestamp() if "T" in tr_ts else float(tr_ts)
                except: tr_ts = 0
            if tr_ts and tr_ts > 1e11: tr_ts /= 1000.0
            if w_s <= tr_ts <= w_s + 300:
                parsed.append({
                    "ts": tr_ts,
                    "sec": int(tr_ts - w_s),
                    "price": float(t.get("price", 0)),
                    "size": float(t.get("size", 0)),
                    "outcome": str(t.get("outcome", "")).upper()
                })
        parsed.sort(key=lambda x: x["ts"])
        
        if not parsed:
            continue
            
        total_candles += 1
        
        # Determine actual candle resolution from final prices
        final_trades = parsed[-10:]
        up_final = [t["price"] for t in final_trades if t["outcome"] in ("UP", "YES")]
        winner = "UP" if (up_final and up_final[-1] > 0.8) else "DOWN"
        
        # Simulation state for this candle
        leg1 = None
        leg2 = None
        
        # Chronological playback of orderbook trades
        for t in parsed:
            # We look for Leg 1 when price <= 0.45 and size >= 5.0
            if leg1 is None:
                if t["price"] <= 0.45 and t["size"] >= 5.0 and t["sec"] <= 240: # within first 4 minutes
                    leg1 = {
                        "outcome": t["outcome"],
                        "price": t["price"],
                        "sec": t["sec"],
                        "max_leg2": round(0.99 - t["price"], 3)
                    }
            elif leg2 is None:
                # We look for opposing Leg 2 where price <= leg1["max_leg2"]
                opp_outcome = "DOWN" if leg1["outcome"] in ("UP", "YES") else "UP"
                is_opp = (opp_outcome == "UP" and t["outcome"] in ("UP", "YES")) or (opp_outcome == "DOWN" and t["outcome"] in ("DOWN", "NO"))
                if is_opp and t["price"] <= leg1["max_leg2"] and t["size"] >= 5.0:
                    leg2 = {
                        "outcome": t["outcome"],
                        "price": t["price"],
                        "sec": t["sec"],
                        "dt": t["sec"] - leg1["sec"]
                    }
                    break # Pair complete!
                    
        candle_time = datetime.datetime.fromtimestamp(w_s, datetime.timezone.utc).strftime("%H:%M")
        
        if leg1 and leg2:
            pairs_completed += 1
            comb = round(leg1["price"] + leg2["price"], 3)
            profit_per_share = round(1.0 - comb, 3)
            profit_usd = round(profit_per_share * 5.0, 3)
            total_pnl += profit_usd
            print(f"✅ {candle_time} UTC | Leg 1: {leg1['outcome']} @ ${leg1['price']:.2f} (T+{leg1['sec']}s) ➔ Leg 2: {leg2['outcome']} @ ${leg2['price']:.2f} (T+{leg2['sec']}s) | Comb: ${comb:.3f} | +${profit_usd:.2f} (Locked)")
            completed_pairs.append({
                "comb": comb,
                "profit": profit_usd,
                "delay": leg2["dt"]
            })
        elif leg1 and not leg2:
            # Held single leg
            leg1_won = (leg1["outcome"] in ("UP", "YES") and winner == "UP") or (leg1["outcome"] in ("DOWN", "NO") and winner == "DOWN")
            if leg1_won:
                single_leg_wins += 1
                gain = round((1.0 - leg1["price"]) * 5.0, 3)
                total_pnl += gain
                print(f"⚠️ {candle_time} UTC | Leg 1: {leg1['outcome']} @ ${leg1['price']:.2f} | Leg 2: MISSED | Outcome: WON +${gain:.2f} (Directional)")
            else:
                single_leg_losses += 1
                loss = round(leg1["price"] * 5.0, 3)
                total_pnl -= loss
                print(f"❌ {candle_time} UTC | Leg 1: {leg1['outcome']} @ ${leg1['price']:.2f} | Leg 2: MISSED | Outcome: LOST -${loss:.2f} (Directional)")
        else:
            print(f"⚪ {candle_time} UTC | No entry condition met (Neither side reached <= $0.45)")
            
    except Exception as e:
        pass

print("\n" + "=" * 65)
print("SPLIT-LEG SIMULATION SUMMARY (PAST 20 CANDLES)")
print("=" * 65)
print(f"Total Candles Evaluated:     {total_candles}")
print(f"Fully Completed Pairs:       {pairs_completed} ({pairs_completed/max(total_candles,1)*100:.1f}%)")
print(f"Single-Leg (Missed Leg 2):   {single_leg_wins + single_leg_losses} (Won: {single_leg_wins}, Lost: {single_leg_losses})")
print(f"Total Simulated PnL (5 sh):  +${total_pnl:.2f}")
if completed_pairs:
    avg_delay = sum(x["delay"] for x in completed_pairs) / len(completed_pairs)
    avg_comb = sum(x["comb"] for x in completed_pairs) / len(completed_pairs)
    print(f"Average Pair Delay:          {avg_delay:.1f} seconds between Leg 1 & Leg 2")
    print(f"Average Completed Pair Cost: ${avg_comb:.3f} ({(1.0 - avg_comb)*100:.1f}% locked profit margin)")
print("=" * 65)
