import requests
import json

# Derive Ethereum address from private key manually using standard ecdsa/keccak
# Or query Polymarket user API
pk = "0x535a7ea810ec26c77dd75ed03798356c27cb70fcd283782e0411e0d896b56b3f"

# We can query Polymarket profiles
# Let's search Polymarket users or inspect how Polymarket creates proxy addresses
print("Searching Polymarket account data...")

# Let's check Polymarket API key owner endpoint if any
api_key = "6d086ea6-ddbb-8f5d-394a-e2cc4b98535c"
api_secret = "ImTZQstMgKq5ftUXDN59CSgtVIxBC4AFG-DfykrnExY="
api_passphrase = "54c46b37fca8f89365b5a2f439494e2539d5bc9a22cee71666b217d25682e383"

# Let's check with py_clob_client on Railway or check what address corresponds to the user's Polymarket account!
