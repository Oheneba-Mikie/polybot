import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*80)
print("🔍 PULLING PREDICT.FUN / BINANCE PREDICTION ORDER BOOK:")
print("="*80)

# Pull markets list from testnet to get active market ID
url = "https://api-testnet.predict.fun/v1/markets"
r = requests.get(url).json()
markets = r.get("data", [])

print(f"Found {len(markets)} active prediction markets on BNB Chain.")

for m in markets[:3]:
    m_id = m.get("id") or m.get("conditionId")
    cat = m.get("categorySlug", "Unknown")
    desc = m.get("description", "")[:60]
    print(f"\n📊 MARKET ID: {m_id}")
    print(f"   Category: {cat}")
    print(f"   Desc:     {desc}...")
    
    # Query orderbook
    try:
        r_ob = requests.get(f"https://api-testnet.predict.fun/v1/markets/{m_id}/orderbook").json()
        data = r_ob.get("data", r_ob)
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        print(f"   Bids count: {len(bids)} | Asks count: {len(asks)}")
        if bids:
            print("   Top 2 Bids:", bids[:2])
        if asks:
            print("   Top 2 Asks:", asks[:2])
    except Exception as e:
        print("   Orderbook error:", e)

print("="*80)
