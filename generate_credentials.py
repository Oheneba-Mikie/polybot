#!/usr/bin/env python3
"""
generate_credentials.py — Derive Polymarket L2 API Key, Secret, and Passphrase from your private key.
Now supports automatic Proxy Wallet (Funder) detection for MetaMask and social wallets.

Usage:
    .\.venv\Scripts\python.exe generate_credentials.py
"""

import os
import sys
import requests
from dotenv import load_dotenv
from eth_account import Account
from py_clob_client_v2 import ClobClient

# Load env variables from .env if present
load_dotenv()

def get_proxy_wallet(eoa_address):
    """Fetches the user's proxy wallet address from the Polymarket API."""
    try:
        url = f"https://polymarket.com/api/profile/userData?address={eoa_address}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("proxyWallet")
    except Exception as e:
        print(f"⚠️ Warning: Could not fetch proxy wallet from Polymarket API: {e}")
    return None

def main():
    print("\n" + "="*70)
    print("  Polymarket L2 API Credentials Generator")
    print("="*70)
    
    # Try reading from .env first
    pk = os.getenv("POLYMARKET_PRIVATE_KEY")
    if pk and pk.startswith("0x") and len(pk) == 66:
        print(f"\nFound private key in .env: {pk[:10]}...{pk[-8:]}")
        try:
            use_env = input("Do you want to use this private key? [Y/n]: ").strip().lower()
        except KeyboardInterrupt:
            print("\nCancelled.")
            return
        if use_env not in ("", "y", "yes"):
            pk = None
            
    if not pk:
        # Prompt user for private key
        try:
            pk = input("\nEnter your new MetaMask 32-byte Private Key (starting with 0x): ").strip()
        except KeyboardInterrupt:
            print("\nCancelled.")
            return

    if not pk.startswith("0x") or len(pk) != 66:
        print("\n❌ Error: Private key must start with '0x' and be exactly 66 characters long.")
        return

    # Derive EOA address
    try:
        eoa_address = Account.from_key(pk).address
        print(f"\nSigner EOA Address: {eoa_address}")
    except Exception as e:
        print(f"\n❌ Error: Invalid private key format: {e}")
        return

    # Resolve Funder/Proxy Wallet
    print("Resolving your Polymarket Proxy Wallet (funder)...")
    proxy_wallet = get_proxy_wallet(eoa_address)
    
    sig_type = 0
    funder_address = eoa_address
    
    if proxy_wallet and proxy_wallet.lower() != eoa_address.lower():
        print(f"👉 Found Proxy Wallet: {proxy_wallet} (holds your USDC)")
        funder_address = proxy_wallet
        sig_type = 3  # POLY_1271 (required for new deposit wallets)
    else:
        print("👉 No active proxy wallet found. Using EOA directly.")
        sig_type = 0  # EOA

    print("\nDeriving credentials from Polymarket L1 signature...")
    try:
        # Initialize client
        client = ClobClient(
            host="https://clob.polymarket.com",
            chain_id=137,  # Polygon Mainnet
            key=pk,
            signature_type=sig_type,
            funder=funder_address
        )
        
        # Derive credentials
        creds = client.create_or_derive_api_key()
        
        print("\n" + "="*70)
        print("  SUCCESS! Copy these values into your .env file:")
        print("="*70)
        print(f"POLYMARKET_PRIVATE_KEY={pk}")
        print(f"POLYMARKET_ADDRESS={funder_address}")
        print(f"POLYMARKET_API_KEY={creds.api_key}")
        print(f"POLYMARKET_API_SECRET={creds.api_secret}")
        print(f"POLYMARKET_API_PASSPHRASE={creds.api_passphrase}")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error deriving credentials: {e}")
        print("Make sure you are connected to the internet and using a valid private key.")

if __name__ == "__main__":
    main()
