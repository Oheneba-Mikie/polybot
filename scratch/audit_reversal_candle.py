import requests
import json
import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

# The 12:10 UTC candle (1787487000)
ts = 1787487000
slug = f"btc-updown-5m-{ts}"

print("="*85)
print(f"🔍 FORENSIC AUDIT OF CANDLE: {slug} (8:10 AM - 8:15 AM ET)")
print("="*85)

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()
if r and r[0].get("markets"):
    mkt = r[0]["markets"][0]
    cid = mkt.get("conditionId")
    question = mkt.get("question")
    print(f"Market Question: {question}")
    
    # Get all trades in this candle
    r_trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=100", timeout=5).json()
    trades = sorted(r_trades, key=lambda x: x.get("timestamp", 0))
    
    print(f"Total trades recorded: {len(trades)}")
    print("-" * 85)
    print(f"{'Time (UTC)':<12} | {'Side':<6} | {'Price':<8} | {'Shares':<10} | {'Note'}")
    print("-" * 85)
    for t in trades:
        ts_sec = t.get("timestamp", 0)
        dt = datetime.datetime.fromtimestamp(ts_sec, datetime.timezone.utc).strftime("%H:%M:%S")
        side = t.get("outcome", "")
        px = float(t.get("price", 0))
        sz = float(t.get("size", 0))
        note = ""
        if 0.84 <= px <= 0.86 and side == "Down":
            note = "<- Entry trigger"
        elif px <= 0.80 and side == "Down":
            note = "<- Reversal / Stop-Loss"
        print(f"{dt:<12} | {side:<6} | ${px:<7.4f} | {sz:<10.1f} | {note}")

# Check Binance 1-minute klines for 12:10 - 12:15 UTC
try:
    r_binance = requests.get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime=1787487000000&endTime=1787487300000", timeout=5).json()
    print("\n" + "="*85)
    print("📈 BINANCE BTC 1-MINUTE CANDLES (12:10 - 12:15 UTC):")
    print("="*85)
    for k in r_binance:
        k_time = datetime.datetime.fromtimestamp(k[0]/1000, datetime.timezone.utc).strftime("%H:%M")
        o, h, l, c = float(k[1]), float(k[2]), float(k[3]), float(k[4])
        print(f"[{k_time} UTC] Open: ${o:.2f} | High: ${h:.2f} | Low: ${l:.2f} | Close: ${c:.2f} | Net: {c-o:+.2f}")
except Exception as e:
    print("Binance check error:", e)

print("="*85)
