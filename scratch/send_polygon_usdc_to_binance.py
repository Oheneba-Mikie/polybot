import os
import json
from dotenv import load_dotenv

load_dotenv()

def transfer_usdc():
    pk = os.getenv("POLYMARKET_PRIVATE_KEY", "0x535a7ea810ec26c77dd75ed03798356c27cb70fcd283782e0411e0d896b56b3f")
    funder = os.getenv("POLYMARKET_ADDRESS", "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8")
    recipient = "0x4cd00e387622c35bddb9b4c962c136462338bc31" # Binance Deposit Address
    amount_usdc = 0.70 # $0.70 USDC
    
    print(f"=== TRANSFERRING ${amount_usdc:.2f} USDC FROM POLYMARKET TO BINANCE ===")
    print(f"Funder: {funder}")
    print(f"Recipient (Binance Deposit): {recipient}")
    
    try:
        from py_clob_client_v2.client import ClobClient
        from py_clob_client_v2.clob_types import ApiCreds, BalanceAllowanceParams, AssetType
        
        creds = ApiCreds(
            api_key=os.getenv("POLYMARKET_API_KEY", ""),
            api_secret=os.getenv("POLYMARKET_API_SECRET", ""),
            api_passphrase=os.getenv("POLYMARKET_API_PASSPHRASE", "")
        )
        
        client = ClobClient(
            host="https://clob.polymarket.com",
            chain_id=137,
            key=pk,
            creds=creds,
            signature_type=3,
            funder=funder
        )
        
        # Check current balance first
        bal_info = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        b_val = float(bal_info.get("balance", "0")) / 1e6
        print(f"Current Polymarket Cash Balance: ${b_val:.4f} USDC")
        
        if b_val < amount_usdc:
            print("Error: Insufficient balance.")
            return

        # Execute ERC20 transfer of USDC from funder to Binance deposit address via Web3
        from web3 import Web3
        
        rpcs = ["https://polygon-bor-rpc.publicnode.com", "https://polygon.drpc.org"]
        w3 = None
        for rpc in rpcs:
            try:
                temp_w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 5}))
                if temp_w3.is_connected():
                    w3 = temp_w3
                    break
            except Exception: pass
            
        if not w3:
            print("Error: Could not connect to Polygon RPC.")
            return

        # USDC.e contract on Polygon: 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174
        usdc_abi = [
            {
                "constant": False,
                "inputs": [
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "transfer",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            }
        ]
        
        usdc_contract = w3.eth.contract(address=Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"), abi=usdc_abi)
        amount_raw = int(amount_usdc * 1e6)
        
        tx = usdc_contract.functions.transfer(
            Web3.to_checksum_address(recipient),
            amount_raw
        ).build_transaction({
            'from': Web3.to_checksum_address(funder),
            'nonce': w3.eth.get_transaction_count(Web3.to_checksum_address(funder)),
            'gasPrice': w3.eth.gas_price,
        })
        
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=pk)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"SUCCESS! Transaction Hash: {w3.to_hex(tx_hash)}")
        
    except Exception as e:
        print(f"Transfer Exception: {e}")

if __name__ == "__main__":
    transfer_usdc()
