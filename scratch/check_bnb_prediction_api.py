import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("="*80)
print("🔍 QUERYING PREDICT.FUN / BNB CHAIN PREDICTION MARKETS API:")
print("="*80)

try:
    r = requests.get("https://api.predict.fun/v1/markets", timeout=5).json()
    print("Markets response keys:", r.keys() if isinstance(r, dict) else len(r))
    if isinstance(r, dict) and "data" in r:
        for m in r["data"][:5]:
            print(f"  • {m.get('title', m.get('question'))} | Status: {m.get('status')}")
    elif isinstance(r, list):
        for m in r[:5]:
            print(f"  • {m.get('title', m.get('question'))}")
except Exception as e:
    print("Predict.fun query error:", e)

# Also check PancakeSwap 5-minute prediction subgraph
try:
    print("\n🥞 QUERYING PANCAKESWAP 5-MINUTE BTC PREDICTION SUBGRAPH (BNB CHAIN):")
    query = """
    {
      rounds(first: 3, orderBy: epoch, orderDirection: desc) {
        epoch
        startBlock
        lockPrice
        closePrice
        totalAmount
        bullAmount
        bearAmount
      }
    }
    """
    subgraph_url = "https://api.thegraph.com/subgraphs/name/pancakeswap/prediction-v2"
    r_sub = requests.post(subgraph_url, json={"query": query}, timeout=5).json()
    rounds = r_sub.get("data", {}).get("rounds", [])
    for rd in rounds:
        print(f"  • Epoch #{rd.get('epoch')} | Bull: {float(rd.get('bullAmount', 0)):.2f} BNB | Bear: {float(rd.get('bearAmount', 0)):.2f} BNB")
except Exception as e:
    print("PancakeSwap query error:", e)
