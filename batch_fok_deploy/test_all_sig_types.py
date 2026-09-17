import os
from dotenv import load_dotenv
from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import ApiCreds, BalanceAllowanceParams, AssetType
from eth_account import Account

load_dotenv("d:/Desktop/antigravity/POLYBOT/polybot/batch_fok_deploy/.env")

private_key = os.getenv("POLYMARKET_PRIVATE_KEY", "")
funder = os.getenv("POLYMARKET_ADDRESS", "")
api_key = os.getenv("POLYMARKET_API_KEY", "")
api_secret = os.getenv("POLYMARKET_API_SECRET", "")
api_passphrase = os.getenv("POLYMARKET_API_PASSPHRASE", "")

acct = Account.from_key(private_key)
print("Signer EOA Address:", acct.address)
print("Configured Funder:", funder)

creds = ApiCreds(
    api_key=api_key,
    api_secret=api_secret,
    api_passphrase=api_passphrase,
)

for sig_type in [0, 1, 2, 3]:
    try:
        c = ClobClient(
            host="https://clob.polymarket.com",
            key=private_key,
            chain_id=137,
            creds=creds,
            signature_type=sig_type,
            funder=funder,
        )
        resp = c.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        raw_b = float(resp.get("balance", 0)) / 1e6
        print(f"[SignatureType={sig_type}] Balance: ${raw_b:.4f} USDC | Allowances: {list(resp.get('allowances', {}).keys())}")
    except Exception as e:
        print(f"[SignatureType={sig_type}] Error: {e}")
