import os
import sys
import requests
from dotenv import load_dotenv
from eth_account import Account
from py_clob_client_v2 import ClobClient

sys.stdout.reconfigure(encoding='utf-8')

print("="*80)
print("🚀 AUTOMATIC POLYMARKET CREDENTIALS & PROXY SETUP")
print("="*80)

env_path = "scalper_bailout_deploy/.env"
load_dotenv(env_path)

pk = os.getenv("POLYMARKET_PRIVATE_KEY")

if not pk or not pk.startswith("0x") or len(pk) != 66:
    print(f"❌ Error: Please open {env_path} and put your new private key in the POLYMARKET_PRIVATE_KEY= line.")
    print("Example: POLYMARKET_PRIVATE_KEY=0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef")
    sys.exit(1)

# Derive EOA address
try:
    eoa_address = Account.from_key(pk).address
    print(f"🔑 Derived Signer Address: {eoa_address}")
except Exception as e:
    print(f"❌ Invalid private key format: {e}")
    sys.exit(1)

# Resolve Proxy Wallet from Polymarket
print("🔍 Resolving your Polymarket Proxy Wallet (funder)...")
proxy_wallet = None
try:
    url = f"https://polymarket.com/api/profile/userData?address={eoa_address}"
    resp = requests.get(url, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        proxy_wallet = data.get("proxyWallet")
except Exception as e:
    print(f"Note on proxy lookup: {e}")

funder_address = proxy_wallet if proxy_wallet else eoa_address
sig_type = 3 if proxy_wallet and proxy_wallet.lower() != eoa_address.lower() else 0

print(f"🏦 Selected Funder / Proxy Address: {funder_address}")
print(f"📝 Signature Type: {sig_type}")

print("\n⚡ Contacting Polymarket CLOB to derive API Key, Secret & Passphrase...")
try:
    client = ClobClient(
        host="https://clob.polymarket.com",
        chain_id=137,
        key=pk,
        signature_type=sig_type,
        funder=funder_address
    )
    creds = client.create_or_derive_api_key()
    
    api_key = creds.api_key
    api_secret = creds.api_secret
    api_passphrase = creds.api_passphrase
    
    print("\n✅ DERIVATION SUCCESSFUL!")
    print(f"   API Key:        {api_key}")
    print(f"   Passphrase:     {api_passphrase}")
    print(f"   API Secret:     {api_secret[:6]}...{api_secret[-4:]}")
    
    # Write to scalper_bailout_deploy/.env
    new_env_content = f"""# Polymarket Live Credentials
POLYMARKET_LIVE_TRADING=true
POLYMARKET_ADDRESS={funder_address}
POLYMARKET_PRIVATE_KEY={pk}
POLYMARKET_API_KEY={api_key}
POLYMARKET_API_SECRET={api_secret}
POLYMARKET_API_PASSPHRASE={api_passphrase}
SIGNATURE_TYPE={sig_type}
"""
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(new_env_content)
        
    print(f"\n💾 Saved all new credentials and proxy address directly to {env_path}!")
    print("="*80)
    
except Exception as e:
    print(f"❌ Error deriving CLOB API keys: {e}")
    print("Make sure your MetaMask account has signed in to Polymarket at least once in your browser!")
    print("="*80)
