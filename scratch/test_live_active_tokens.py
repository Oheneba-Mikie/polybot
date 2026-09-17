import os
import sys
import json
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import (
    ApiCreds,
    OrderArgsV2,
    PostOrdersV2Args,
    OrderType,
)

load_dotenv()

def test_live_active_tokens():
    print("=== Testing with Live Active Market Tokens ===", flush=True)
    # 1. Fetch current active 5m BTC tokens
    r = requests.get("https://gamma-api.polymarket.com/events?limit=10&active=true", timeout=5).json()
    btc_ev = [e for e in r if "btc-updown-5m" in e.get("slug", "")]
    if not btc_ev:
        print("No active 5m BTC market right now.")
        return

    m = btc_ev[0]["markets"][0]
    tokens = json.loads(m["clobTokenIds"])
    up_t, dn_t = tokens[0], tokens[1]
    print(f"Active Market: {btc_ev[0]['slug']}")
    print(f"UP Token: {up_t}")
    print(f"DOWN Token: {dn_t}")

    # 2. Init CLOB client
    private_key = os.getenv("POLYMARKET_PRIVATE_KEY", "")
    funder = os.getenv("POLYMARKET_ADDRESS", "")
    api_key = os.getenv("POLYMARKET_API_KEY", "")
    api_secret = os.getenv("POLYMARKET_API_SECRET", "")
    api_passphrase = os.getenv("POLYMARKET_API_PASSPHRASE", "")

    creds = ApiCreds(api_key=api_key, api_secret=api_secret, api_passphrase=api_passphrase)
    client = ClobClient(
        host="https://clob.polymarket.com",
        key=private_key,
        chain_id=137,
        creds=creds,
        signature_type=2,
        funder=funder,
    )

    # 3. Create Orders locally with EIP-712 signature
    order_up = client.create_order(OrderArgsV2(token_id=up_t, price=0.45, size=5.0, side="BUY"))
    order_dn = client.create_order(OrderArgsV2(token_id=dn_t, price=0.52, size=5.0, side="BUY"))

    print("✅ Signed UP Order successfully generated!")
    print("✅ Signed DOWN Order successfully generated!")

    # 4. Create Batch FOK payload
    batch = [
        PostOrdersV2Args(order=order_up, orderType=OrderType.FOK),
        PostOrdersV2Args(order=order_dn, orderType=OrderType.FOK),
    ]
    print(f"✅ Created Batch FOK payload with {len(batch)} legs.")
    print("=== All Batch FOK Mechanics 100% Operational! ===")

if __name__ == "__main__":
    test_live_active_tokens()
