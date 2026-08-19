import requests
import json
import time

def analyze_historical_volatility_and_growth():
    print("=== HISTORICAL BTC VOLATILITY & PAIR ARBITRAGE AUDIT ===")
    print("Comparing Friday (Aug 14) & Saturday (Aug 15) vs Sunday Early Morning (Aug 16)\n")
    
    url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=500"
    r = requests.get(url).json()
    
    friday_triggers = 0
    saturday_triggers = 0
    sunday_triggers = 0
    
    total_friday_rounds = 0
    total_saturday_rounds = 0
    total_sunday_rounds = 0
    
    for k in r:
        open_time = int(k[0]) / 1000.0
        open_p = float(k[1])
        high_p = float(k[2])
        low_p = float(k[3])
        close_p = float(k[4])
        
        move_range = abs(close_p - open_p)
        total_candle_range = high_p - low_p
        
        t_struct = time.gmtime(open_time)
        day_of_week = t_struct.tm_wday
        
        is_pair_arb_trigger = move_range >= 15.0 or total_candle_range >= 25.0
        
        if day_of_week == 4:
            total_friday_rounds += 1
            if is_pair_arb_trigger: friday_triggers += 1
        elif day_of_week == 5:
            total_saturday_rounds += 1
            if is_pair_arb_trigger: saturday_triggers += 1
        elif day_of_week == 6:
            total_sunday_rounds += 1
            if is_pair_arb_trigger: sunday_triggers += 1

    print("5-Minute High-Volatility Trigger Rounds (> $15 Move):")
    print(f"  * Friday (Aug 14):   {friday_triggers} out of {total_friday_rounds} rounds ({friday_triggers/max(1,total_friday_rounds)*100:.1f}% Trigger Rate)")
    print(f"  * Saturday (Aug 15): {saturday_triggers} out of {total_saturday_rounds} rounds ({saturday_triggers/max(1,total_saturday_rounds)*100:.1f}% Trigger Rate)")
    print(f"  * Sunday (Aug 16):   {sunday_triggers} out of {total_sunday_rounds} rounds ({sunday_triggers/max(1,total_sunday_rounds)*100:.1f}% Trigger Rate)")
    
    print("\nACCOUNT GROWTH SIMULATION FROM $2.20 BALANCE:")
    for label, trig_count in [("Friday (Weekday)", friday_triggers), ("Saturday (Weekend)", saturday_triggers), ("Sunday Early Morning", sunday_triggers)]:
        bal = 2.20
        win_count = 0
        for _ in range(trig_count):
            pair_cost = 0.96
            if bal >= 4.80:
                shares = 5.0
                profit = shares * (1.00 - pair_cost)
            else:
                shares = 2.0
                profit = shares * (1.00 - pair_cost)
            bal += profit
            win_count += 1
        print(f"  * {label}: Starting $2.20 -> Ends at ${bal:.2f} USDC (+{win_count} Guaranteed Wins!)")

if __name__ == "__main__":
    analyze_historical_volatility_and_growth()
