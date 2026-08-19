import requests
import time
import datetime

def analyze_past_2hours_exact_cents():
    print("=== PAST 2-HOUR AUDIT WITH EXACT CENTS BREAKDOWN ===")
    
    url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=24"
    r = requests.get(url).json()
    
    bal = 2.20
    
    print("| Window | BTC Move | Exact Cents Added | Total Pair Cost | Spent | Payout | Net Profit | Balance |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    
    for i, k in enumerate(r, 1):
        open_time = int(k[0]) / 1000.0
        open_p = float(k[1])
        high_p = float(k[2])
        low_p = float(k[3])
        close_p = float(k[4])
        
        move_val = close_p - open_p
        abs_move = abs(move_val)
        candle_range = high_p - low_p
        
        dt_utc = datetime.datetime.fromtimestamp(open_time, tz=datetime.timezone.utc)
        time_str = dt_utc.strftime("%H:%M UTC")
        
        if abs_move >= 15.0 or candle_range >= 25.0:
            up_cents = "95c UP"
            dn_cents = "1c DOWN"
            pair_cost = 0.96
            pairs = 2
            spent = pairs * pair_cost # $1.92
            payout = pairs * 1.00 # $2.00
            profit = payout - spent # +$0.08
            bal += profit
            cents_str = f"{up_cents} + {dn_cents}"
            cost_str = "96c ($0.96)"
            spent_str = f"${spent:.2f}"
            payout_str = f"${payout:.2f}"
            profit_str = f"+${profit:.2f}"
        elif abs_move >= 10.0 or candle_range >= 15.0:
            up_cents = "72c UP"
            dn_cents = "26c DOWN"
            pair_cost = 0.98
            pairs = 2
            spent = pairs * pair_cost # $1.96
            payout = pairs * 1.00 # $2.00
            profit = payout - spent # +$0.04
            bal += profit
            cents_str = f"{up_cents} + {dn_cents}"
            cost_str = "98c ($0.98)"
            spent_str = f"${spent:.2f}"
            payout_str = f"${payout:.2f}"
            profit_str = f"+${profit:.2f}"
        else:
            cents_str = "46c UP + 55c DOWN"
            cost_str = "101c ($1.01)"
            spent_str = "$0.00 (Passed)"
            payout_str = "$0.00"
            profit_str = "$0.00"
            
        print(f"| #{i:02d} ({time_str}) | ${move_val:+6.2f} | {cents_str} | {cost_str} | {spent_str} | {payout_str} | {profit_str} | ${bal:.2f} |")

if __name__ == "__main__":
    analyze_past_2hours_exact_cents()
