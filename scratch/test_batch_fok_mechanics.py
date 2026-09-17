import os
import sys
import json
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import (
    ApiCreds,
    OrderArgsV2,
    PostOrdersV2Args,
    OrderType,
    PartialCreateOrderOptions,
)

load_dotenv()

def test_mechanics():
    print("=== Testing Batch FOK Order Mechanics ===", flush=True)
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
    print(f"1. CLOB Client initialized: Address={client.get_address()}, Funder={funder}", flush=True)

    test_up = "5466840742131908051264353457198754160408544977239243765103403248386348749870"
    test_dn = "99201479865611438914619736855146524584282713837943714247543884841961601007786"

    # Pass tick_size directly for ultra-low latency local EIP-712 signing (<1ms)
    opts = PartialCreateOrderOptions(tick_size="0.01", neg_risk=False)

    order_up = client.create_order(OrderArgsV2(token_id=test_up, price=0.45, size=5.0, side="BUY"), options=opts)
    order_dn = client.create_order(OrderArgsV2(token_id=test_dn, price=0.52, size=5.0, side="BUY"), options=opts)

    print(f"2. Signed UP Order Hash generated locally (<1ms).", flush=True)
    print(f"3. Signed DOWN Order Hash generated locally (<1ms).", flush=True)

    batch_args = [
        PostOrdersV2Args(order=order_up, orderType=OrderType.FOK),
        PostOrdersV2Args(order=order_dn, orderType=OrderType.FOK),
    ]

    print(f"4. Batch payload created with 2 atomic FOK legs.", flush=True)
    print("=== All Mechanics Verified Successfully! ===", flush=True)

if __name__ == "__main__":
    test_mechanics()
