pk = None
funder = None
with open("D:/Desktop/antigravity/POLYBOT/polybot/.env", "r") as f:
    for line in f:
        if line.startswith("POLYMARKET_PRIVATE_KEY="):
            pk = line.strip().split("=")[1]
        elif line.startswith("POLYMARKET_ADDRESS="):
            funder = line.strip().split("=")[1]

from py_clob_client_v2.client import ClobClient
client = ClobClient(
    host="https://clob.polymarket.com",
    key=pk,
    chain_id=137,
    signature_type=3,
    funder=funder
)
api_creds = client.create_or_derive_api_creds()
client.set_api_creds(api_creds)

try:
    bal = client.get_balance()
    print("CLOB get_balance():", bal)
except Exception as e:
    print("CLOB get_balance error:", e)

try:
    allowance = client.get_balance_allowance()
    print("CLOB get_balance_allowance():", allowance)
except Exception as e:
    print("CLOB allowance error:", e)
