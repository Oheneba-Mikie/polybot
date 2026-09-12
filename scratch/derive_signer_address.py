import os
import sys
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv("scalper_bailout_deploy/.env")

from eth_account import Account

pk = os.getenv("POLYMARKET_PRIVATE_KEY") or os.getenv("PK")
if pk:
    acct = Account.from_key(pk)
    print("="*80)
    print("🔑 DERIVED SIGNER ADDRESS FROM PRIVATE KEY IN .ENV:")
    print(f"   Address: {acct.address}")
    print("="*80)
else:
    print("No private key found in .env")
