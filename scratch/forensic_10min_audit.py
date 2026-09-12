import requests
import json
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

# Candle 1: 13:00 - 13:05 UTC (ts = 1787662800)
# Candle 2: 13:05 - 13:10 UTC (ts = 1787663100)

print("="*95)
print(f"📊 10-MINUTE COMPLETE RAW AUDIT (13:00 UTC - 13:10 UTC)")
print("="*95)

# 1. Fetch Railway Bot State & All Logs
print("\n--- 1. RAILWAY BOT STATE & LOGS ---")
try:
    r_state = requests.get("https://polybot-97-scalper-production.up.railway.app/api/state", timeout=4).json()
    print(f"Status:          {r_state.get('status')}")
    print(f"Balance:         ${r_state.get('balance')}")
    print(f"Total Trades:    {r_state.get('total_trades')}")
    print(f"Strike at Open:  ${r_state.get('strike_price')}")
    print(f"Strike Gap:      ${r_state.get('strike_gap')}")
    print(f"Chainlink BTC:   ${r_state.get('chainlink_price')}")
    print("Bot Logs:")
    for l in r_state.get("logs", []):
        print(f"  {l}")
except Exception as e:
    print(f"Railway error: {e}")

# 2. Audit 13:05 - 13:10 UTC Candle (1787663100)
print("\n--- 2. CANDLE 13:05 - 13:10 UTC (btc-updown-5m-1787663100) ---")
slug_1305 = "btc-updown-5m-1787663100"
r_evt = requests.get(f"{GAMMA_HOST}/events?slug={slug_1305}", timeout=4).json()
if r_evt and r_evt[0].get("markets"):
    m = r_evt[0]["markets"][0]
    cid = m.get("conditionId")
    print(f"Question:        {m.get('question')}")
    print(f"Resolution:      {m.get('outcomePrices')}")
    print(f"Closed:          {m.get('closed')}")
    
    # Check trades on market
    r_tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=100", timeout=4).json()
    print(f"Total market trades: {len(r_tr)}")
    print("\nTrades in final 60 seconds (13:09:00 - 13:10:00 UTC):")
    for t in reversed(r_tr):
        ts = t.get("timestamp", 0)
        dt = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%H:%M:%S")
        px = float(t.get("price", 0))
        out = t.get("outcome", "")
        sz = float(t.get("size", 0))
        if ts >= 1787663100 + 240: # final 60s
            print(f"  [{dt}] {out:<4} | {sz:>6.2f} sh @ ${px:.4f}")

# 3. Check Binance 1m price for 13:05 - 13:10
print("\n--- 3. BINANCE 1-MINUTE CANDLES (13:05 - 13:10 UTC) ---")
r_k = requests.get("https://api.binance.com/api/v3/klines", 
                   params={"symbol":"BTCUSDT", "interval":"1m", "startTime":1787663100*1000, "endTime":(1787663100+300)*1000}, 
                   timeout=4).json()
for k in r_k:
    dt = datetime.datetime.fromtimestamp(k[0]/1000, datetime.timezone.utc).strftime("%H:%M")
    print(f"  [{dt}] Open: ${float(k[1]):.2f} | High: ${float(k[2]):.2f} | Low: ${float(k[3]):.2f} | Close: ${float(k[4]):.2f}")

print("="*95)
