import requests
import json
import datetime
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

print("="*95)
print("🔍 COMPLETE STEP-BY-STEP AUDIT: RAILWAY LOGS vs CODE vs POLYMARKET API")
print("="*95)

# 1. Fetch Railway Logs
print("\n--- 1. RAILWAY CONTAINER LOGS (VERBATIM) ---")
try:
    r_state = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=4).json()
    logs = r_state.get("logs", [])
    for l in logs:
        print(f"  {l}")
except Exception as e:
    print(f"Error fetching logs: {e}")

# 2. Forensic Window-by-Window Code Condition Simulation
windows = [
    (1787663400, "13:10 - 13:15 UTC"),
    (1787663700, "13:15 - 13:20 UTC"),
    (1787664000, "13:20 - 13:25 UTC"),
    (1787664300, "13:25 - 13:30 UTC"),
]

print("\n--- 2. WINDOW-BY-WINDOW EVALUATION AGAINST CODE CONDITIONS ---")
for ts, label in windows:
    slug = f"btc-updown-5m-{ts}"
    print(f"\n📁 Window: {label} ({slug})")
    
    # Fetch Market Info from Gamma
    r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
    if not r_evt or not r_evt[0].get("markets"):
        print("  ❌ Market Info: Gamma API returned None (Skipped at line: 'if not cached_market')")
        continue
    
    mkt = r_evt[0]["markets"][0]
    cid = mkt.get("conditionId")
    tids = json.loads(mkt.get("clobTokenIds", "[]"))
    up_id, dn_id = tids[0], tids[1]
    
    # Fetch Strike at open from Binance
    r_k = requests.get("https://api.binance.com/api/v3/klines", 
                       params={"symbol": "BTCUSDT", "interval": "5m", "startTime": ts * 1000, "limit": 1}, 
                       timeout=2).json()
    strike = float(r_k[0][1]) if r_k else None
    
    # Fetch final 1m candle close price
    r_k_final = requests.get("https://api.binance.com/api/v3/klines", 
                             params={"symbol": "BTCUSDT", "interval": "1m", "startTime": (ts+240) * 1000, "limit": 1}, 
                             timeout=2).json()
    final_btc = float(r_k_final[0][4]) if r_k_final else None
    gap = abs(final_btc - strike) if (final_btc and strike) else 0.0
    
    # Fetch trades that occurred in final 35s of this window
    r_tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=100", timeout=3).json()
    final_35s_trades = [t for t in r_tr if ts + 265 <= t.get("timestamp", 0) <= ts + 292]
    
    # Check Order book prices during window
    print(f"  • Strike Price at Open: ${strike:.2f}")
    print(f"  • Final 35s BTC Price:  ${final_btc:.2f} (Gap: ${gap:.2f})")
    print(f"  • Condition 'gap < 25.0': {'BLOCKED (Gap too small)' if gap < 25.0 else 'PASSED'}")
    print(f"  • Trades in final 35s on Polymarket CLOB: {len(final_35s_trades)}")
    if final_35s_trades:
        for t in final_35s_trades[:3]:
            print(f"     -> {t.get('outcome')} {t.get('size')} sh @ ${float(t.get('price')):.4f}")
    else:
        print("     -> 0 trades executed on the entire Polymarket book in the final 35s")

print("="*95)
