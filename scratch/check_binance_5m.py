import requests
import datetime

print("="*80)
print("FETCHING REAL-TIME 5-MINUTE BTC DATA FROM BINANCE (PUBLIC API)")
print("="*80)

# 1. Fetch 5m BTC/USDT spot candles
url = "https://api.binance.com/api/v3/klines"
params = {
    "symbol": "BTCUSDT",
    "interval": "5m",
    "limit": 12 # Last 1 hour (12 five-minute cycles)
}

try:
    r = requests.get(url, params=params, timeout=5).json()
    print(f"{'Time (UTC)':<12} | {'Open':<10} | {'High':<10} | {'Low':<10} | {'Close':<10} | {'Change ($)':<12} | {'Direction'}")
    print("-" * 80)
    
    for k in r:
        open_time = datetime.datetime.fromtimestamp(k[0]/1000.0, tz=datetime.timezone.utc).strftime('%H:%M:%S')
        o = float(k[1])
        h = float(k[2])
        l = float(k[3])
        c = float(k[4])
        diff = c - o
        direction = "UP  " if diff >= 0 else "DOWN"
        print(f"{open_time:<12} | ${o:<9.2f} | ${h:<9.2f} | ${l:<9.2f} | ${c:<9.2f} | {diff:>+10.2f} | {direction}")

except Exception as e:
    print(f"Error querying Binance API: {e}")

# 2. Check 24hr Stats
try:
    t24 = requests.get("https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT", timeout=5).json()
    print("-" * 80)
    print(f"BINANCE BTC/USDT 24H STATS:")
    print(f"  Current Price:  ${float(t24['lastPrice']):,.2f}")
    print(f"  24h High:       ${float(t24['highPrice']):,.2f}")
    print(f"  24h Low:        ${float(t24['lowPrice']):,.2f}")
    print(f"  24h Change:     {float(t24['priceChangePercent']):+.2f}%")
    print("=" * 80)
except Exception as e:
    print("Error 24hr stats:", e)
