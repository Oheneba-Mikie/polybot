import requests
import json
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

target_addr = "0x639f7e0b317f586b350cdcc1ceb22a2ed44e2211"
GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST = "https://data-api.polymarket.com"
rpc_url = "https://polygon-bor-rpc.publicnode.com"

print("="*95)
print(f"🔍 PULLING ALL PUBLIC METADATA & ON-CHAIN ACTIVITY FOR: {target_addr}")
print("="*95)

# 1. Check Polymarket Gamma User Profile
try:
    r_user = requests.get(f"{GAMMA_HOST}/users/{target_addr}", timeout=5).json()
    print("👤 Polymarket Profile Metadata:")
    print(f"   • Username:     {r_user.get('name', 'None')}")
    print(f"   • Proxy Wallet: {r_user.get('proxyWallet', 'None')}")
    print(f"   • Created At:   {r_user.get('createdAt', 'None')}")
    print(f"   • Raw:          {r_user}")
except Exception as e:
    print("   Profile query error:", e)

# 2. Check Polymarket Activity
try:
    r_act = requests.get(f"{DATA_HOST}/activity?user={target_addr}&limit=10", timeout=5).json()
    print(f"\n📊 Polymarket Activity Records for {target_addr} ({len(r_act)} found):")
    for a in r_act:
        dt = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(a.get("timestamp", 0)))
        print(f"   • [{dt}] Type: {a.get('type')} | Amount: {a.get('usdcSize') or a.get('size')} | {a.get('title', a.get('asset'))}")
except Exception as e:
    print("   Activity query error:", e)

# 3. Check native POL (MATIC) balance & transaction count on Polygon RPC
try:
    p_bal = {"jsonrpc":"2.0","method":"eth_getBalance","params":[target_addr, "latest"],"id":1}
    r_bal = requests.post(rpc_url, json=p_bal, timeout=5).json()
    matic_bal = int(r_bal.get("result", "0x0"), 16) / 1e18
    
    p_cnt = {"jsonrpc":"2.0","method":"eth_getTransactionCount","params":[target_addr, "latest"],"id":2}
    r_cnt = requests.post(rpc_url, json=p_cnt, timeout=5).json()
    nonce = int(r_cnt.get("result", "0x0"), 16)
    
    print(f"\n🌐 Polygon On-Chain Stats:")
    print(f"   • Native POL Balance:       {matic_bal:.6f} POL")
    print(f"   • Outgoing TX Count (Nonce): {nonce}")
except Exception as e:
    print("   RPC Stats error:", e)

print("="*95)
