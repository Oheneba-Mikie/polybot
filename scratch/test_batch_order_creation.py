import os
import json
from dotenv import load_dotenv

load_dotenv("d:/Desktop/antigravity/POLYBOT/polybot/scalper_bailout_deploy/.env")

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import OrderArgs, PostOrdersV2Args, OrderType, ApiCreds

pk = os.getenv("POLYMARKET_PRIVATE_KEY")
address = os.getenv("POLYMARKET_ADDRESS")
api_key = os.getenv("POLYMARKET_API_KEY")
api_secret = os.getenv("POLYMARKET_API_SECRET")
api_passphrase = os.getenv("POLYMARKET_PASSPHRASE")

creds = ApiCreds(api_key=api_key, api_secret=api_secret, api_passphrase=api_passphrase)
client = ClobClient(
    host="https://clob.polymarket.com",
    key=pk,
    chain_id=137,
    creds=creds,
    signature_type=2,
    funder=address
)

print("ClobClient initialized successfully!")
print("Client address:", client.get_address())

# Test creating signed orders for both sides
dummy_token_up = "7658597318980911831069111173709893953252535527669330135967292902830030112107"
dummy_token_down = "9807332076037063742172322570234445579609819769545289913549928916407014078849"

order1 = client.create_order(OrderArgs(price=0.38, size=5.0, side="BUY", token_id=dummy_token_up))
order2 = client.create_order(OrderArgs(price=0.58, size=5.0, side="BUY", token_id=dummy_token_down))

print("Order 1 signed successfully:", type(order1))
print("Order 2 signed successfully:", type(order2))

post_args = [
    PostOrdersV2Args(order=order1, orderType=OrderType.GTC),
    PostOrdersV2Args(order=order2, orderType=OrderType.GTC)
]
print("PostOrdersV2Args constructed cleanly with 2 batch items!")
