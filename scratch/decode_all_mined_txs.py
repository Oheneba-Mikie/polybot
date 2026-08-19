import urllib.request
import json

def decode_txs():
    addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    print(f"=== DECODING MINED TRANSACTIONS FOR {addr} ===")
    
    # Query BscScan API
    url = f"https://api.bscscan.com/api?module=account&action=tokentx&address={addr}&startblock=0&endblock=99999999&sort=desc"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        res = urllib.request.urlopen(req, timeout=5)
        txs = json.loads(res.read().decode('utf-8')).get("result", [])
        print(f"Found {len(txs)} Token Transfers:")
        if isinstance(txs, list):
            for t in txs[:5]:
                print(f"   Tx: {t.get('hash')}")
                print(f"   From: {t.get('from')}")
                print(f"   To: {t.get('to')}")
                print(f"   Value: {float(t.get('value', 0)) / 1e18:.4f} {t.get('tokenSymbol')}")
    except Exception as e:
        print("API error:", e)

if __name__ == "__main__":
    decode_txs()
