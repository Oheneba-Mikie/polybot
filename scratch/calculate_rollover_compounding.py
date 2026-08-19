import math

def calculate_rollover():
    print("=== GEOMETRIC COMPOUNDING / ROLLOVER SIMULATION ===")
    print("Starting Balance: $2.20 USDC | Strategy: Full Balance Rollover\n")
    
    pair_cost = 0.96 # 96c total pair cost (95c UP + 1c DOWN)
    profit_per_pair = 1.00 - pair_cost # +$0.04 per pair (+4.167% ROI)
    
    bal = 2.20
    print(f"Start: Balance = ${bal:.2f} USDC")
    
    milestones = [5, 10, 20, 30, 50, 75, 100, 165]
    
    for trade_num in range(1, 166):
        # Full balance reinvestment / rollover: buy max integer pairs allowed by cash
        pairs = math.floor(bal / pair_cost)
        if pairs < 1: pairs = 1
        
        cost = pairs * pair_cost
        payout = pairs * 1.00
        net_gain = payout - cost
        
        bal += net_gain
        
        if trade_num in milestones:
            print(f"Trade #{trade_num:3d}: Balance = ${bal:10.2f} USDC (Sized {pairs:5d} Pairs | Net Gain: +${net_gain:7.2f})")

if __name__ == "__main__":
    calculate_rollover()
