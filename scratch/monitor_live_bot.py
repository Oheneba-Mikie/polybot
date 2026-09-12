import requests
import json
import time
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print("🔍 LIVE SYSTEM AUDIT: CHECKING TOP-UP BALANCE, RAILWAY LOGS & MARKET SCANNER")
print("="*95)

try:
    r = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=5).json()
    
    status = r.get("status")
    cur_candle = r.get("current_candle")
    strike = r.get("strike_price")
    live_btc = r.get("chainlink_price")
    gap = r.get("gap")
    bal = r.get("balance_usdc")
    phase = r.get("phase")
    total_trades = r.get("total_trades")
    wins = r.get("wins")
    losses = r.get("losses")
    streak = r.get("streak")
    profit = r.get("total_profit_usdc")
    
    print(f"📊 LIVE BOT STATUS:       {status}")
    print(f"💰 LIVE WALLET BALANCE:   ${bal if bal is not None else 0.0:.2f} USDC")
    print(f"🏷️ ACTIVE PHASE:          {phase}")
    print(f"📈 LIVE BTC PRICE:        ${live_btc:.2f} | STRIKE: ${strike if strike else 0:.2f} | GAP: ${gap:.2f}")
    print(f"🕯️ CURRENT CANDLE:        {cur_candle}")
    print(f"🏆 PERFORMANCE:           {wins} Wins / {losses} Losses | Streak: {streak} | Profit: ${profit:.2f} USDC\n")
    
    print("📜 RECENT LIVE ENGINE LOGS:")
    print("-" * 80)
    for log_entry in r.get("logs", [])[-15:]:
        print(f"  {log_entry}")
    print("-" * 80)
    
except Exception as e:
    print(f"Error querying live state: {e}")

print("="*95)
