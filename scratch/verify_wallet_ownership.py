import os
from dotenv import load_dotenv
from eth_account import Account
import requests

load_dotenv("scalper_bailout_deploy/.env")

pk = os.getenv("POLYMARKET_PRIVATE_KEY")
env_addr = os.getenv("POLYMARKET_ADDRESS")

acct = Account.from_key(pk)
derived_eoa = acct.address

print("="*70)
print(f"DERIVED EOA FROM PRIVATE KEY: {derived_eoa}")
print(f"POLYMARKET_ADDRESS IN .ENV:  {env_addr}")
print("="*70)

# Check Polymarket profile
r = requests.get(f"https://data-api.polymarket.com/activity?user={env_addr}&limit=1").json()
if r:
    print(f"Polymarket Username: {r[0].get('name')}")
    print(f"Pseudonym:           {r[0].get('pseudonym')}")
    print(f"Proxy Wallet:        {r[0].get('proxyWallet')}")
