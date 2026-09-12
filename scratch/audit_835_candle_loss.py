import requests
import json
import datetime
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Market: btc-updown-5m-1787488500 (Aug 23, 8:35AM - 8:40AM ET = 12:35:00 UTC to 12:40:00 UTC)
GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST = "https://data-api.polymarket.com"
CLOB_HOST = "https://clob.polymarket.com"
WALLET = "0x89B489569F1B2384ee02E958444aF6091219bfe9"

slug = "btc-updown-5m-1787488500"

print("="*90)
print(f"📊 FORENSIC AUDIT OF CANDLE: {slug} (Aug 23, 8:35AM - 8:40AM ET)")
print("="*90)

# 1. Market info
r_mkt = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()
if r_mkt and r_mkt[0].get("markets"):
    m = r_mkt[0]["markets"][0]
    print(f"Question: {m.get('question')}")
    print(f"Resolution outcome: {m.get('outcomePrices')} | Closed: {m.get('closed')}")
    clob_tokens = json.loads(m.get("clobTokenIds", "[]"))
    print(f"Token IDs: UP={clob_tokens[0] if len(clob_tokens)>0 else None} | DOWN={clob_tokens[1] if len(clob_tokens)>1 else None}")

# 2. Binance 1m price data for 12:35 to 12:40 UTC (Timestamp: 1787488500 * 1000 = 1787488500000)
# Note: 1787488500 in ms is 1787488500000. Let's convert to ms
start_ms = 1787488500 * 1000
end_ms = 1787488800 * 1000

print("\n📈 BINANCE BTC/USDT 1-MINUTE CANDLES (12:35 - 12:40 UTC):")
try:
    r_klines = requests.get(
        "https://api.binance.com/api/v3/klines",
        params={"symbol": "BTCUSDT", "interval": "1m", "startTime": start_ms - 60000, "endTime": end_ms + 60000},
        timeout=5
    ).json()
    for k in r_klines:
        t_ms = k[0]
        dt = datetime.datetime.fromtimestamp(t_ms/1000, datetime.timezone.utc).strftime("%H:%M:%S")
        o, h, l, c, v = float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])
        print(f"[{dt}] Open: ${o:.2f} | High: ${h:.2f} | Low: ${l:.2f} | Close: ${c:.2f} | Vol: {v:.2f} BTC")
except Exception as e:
    print(f"Binance fetch error: {e}")

# 3. Polymarket trades on this token during this candle
print("\n📜 ALL TRADES FOR WALLET ON THIS CANDLE:")
r_trades = requests.get(f"{DATA_HOST}/trades?user={WALLET}&limit=50", timeout=5).json()
for t in r_trades:
    if "8:35AM-8:40AM" in t.get("title", ""):
        dt = datetime.datetime.fromtimestamp(t.get("timestamp", 0), datetime.timezone.utc).strftime("%H:%M:%S")
        print(f"[{dt}] {t.get('side')} {t.get('outcome')} | {t.get('size')} sh @ ${t.get('price')} (${t.get('usdcSize')})")

print("="*90)
