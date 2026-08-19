import math

def calculate_hybrid_timeline_to_1000():
    print("=== HYBRID TURBO SYSTEM: TIMELINE TO $1,000.00 USDC ===")
    print("Starting Balance: $2.20 USDC\n")
    
    # Hybrid Average ROI per trade combining Fast Scalps (+42.8% ROI) & Pair Lock (+4.17% ROI)
    # Average blend across active trading hours = ~15.0% Net ROI per trade
    roi_per_trade = 0.15
    
    bal = 2.20
    trades_count = 0
    
    milestones = [10, 25, 50, 100, 250, 500, 1000]
    m_idx = 0
    
    print("| Trade # | Average Stake Spent | Net Profit | Balance | Days @ 15 Trades/Day |")
    print("| :--- | :--- | :--- | :--- | :--- |")
    print(f"| Start | $0.00 | $0.00 | **${bal:.2f}** | Day 0.0 |")
    
    while bal < 1000.0 and trades_count < 200:
        trades_count += 1
        
        # Micro stake allocation capped at 80% of cash
        stake = bal * 0.75
        profit = stake * roi_per_trade
        bal += profit
        
        days = trades_count / 15.0 # ~15 active trades per day
        
        if m_idx < len(milestones) and bal >= milestones[m_idx]:
            print(f"| #{trades_count:3d} | ${stake:8.2f} | +${profit:7.2f} | **${bal:9.2f}** | **Day {days:.1f}** |")
            while m_idx < len(milestones) and bal >= milestones[m_idx]:
                m_idx += 1

if __name__ == "__main__":
    calculate_hybrid_timeline_to_1000()
