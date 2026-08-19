import urllib.request
import json

def test_lifi_quote():
    print("=== TESTING LI.FI CROSS-CHAIN BRIDGE QUOTE (BSC -> POLYGON) ===")
    
    # BSC chainId: 56, Polygon chainId: 137
    # BSC-USD: 0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d
    # Polygon USDC.e: 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174
    
    from_token = "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d"
    to_token = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    from_address = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    amount = "3310000000000000000" # 3.31 USDC (18 decimals on BSC)
    
    url = f"https://li.quest/v1/quote?fromChain=56&toChain=137&fromToken={from_token}&toToken={to_token}&fromAddress={from_address}&fromAmount={amount}"
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        res = urllib.request.urlopen(req, timeout=5)
        r_json = json.loads(res.read().decode('utf-8'))
        
        estimate = r_json.get("estimate", {})
        to_amount = float(estimate.get("toAmount", 0)) / 1e6
        print(f"Success! Li.Fi Bridge Quote Output: ${to_amount:.4f} USDC on Polygon")
        print("Gas cost estimate included in quote!")
    except Exception as e:
        print(f"Error fetching quote: {e}")

if __name__ == "__main__":
    test_lifi_quote()
