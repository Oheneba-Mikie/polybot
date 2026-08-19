import urllib.request
import json

def inspect_proxy_creation():
    proxy_addr = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    print(f"=== INSPECTING CREATION OF PROXY {proxy_addr} ON POLYGON ===")
    
    # Query PolygonScan API
    url = f"https://api.polygonscan.com/api?module=account&action=txlistinternal&address={proxy_addr}&startblock=0&endblock=99999999&sort=asc"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        res = urllib.request.urlopen(req, timeout=5)
        data = json.loads(res.read().decode('utf-8'))
        txs = data.get("result", [])
        if isinstance(txs, list):
            print(f"Found {len(txs)} Internal Txs:")
            for t in txs[:5]:
                print(f"   From: {t.get('from')}")
                print(f"   To: {t.get('to')}")
                print(f"   Hash: {t.get('hash')}")
                print(f"   Type: {t.get('type')}")
        else:
            print("API Output:", txs)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    inspect_proxy_creation()
