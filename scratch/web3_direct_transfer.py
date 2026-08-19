import os, json
from dotenv import load_dotenv
from web3 import Web3
from eth_account import Account

load_dotenv()

def run_web3_transfer():
    pk = os.getenv("POLYMARKET_PRIVATE_KEY", "0x535a7ea810ec26c77dd75ed03798356c27cb70fcd283782e0411e0d896b56b3f")
    w3 = Web3(Web3.HTTPProvider("https://bsc-dataseed.binance.org"))
    
    sender_acct = Account.from_key(pk)
    sender = sender_acct.address # 0x0159010e49e7Db204a897819a787f41CFe1F2C67
    funder = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    
    print(f"=== SENDER KEY DERIVED TO: {sender} ===")
    print(f"=== FUNDER TARGET: {funder} ===")
    
    # Check BNB balance of both
    b_sender = w3.eth.get_balance(sender) / 1e18
    b_funder = w3.eth.get_balance(funder) / 1e18
    print(f"BNB Sender (0x0159...): {b_sender:.6f} BNB")
    print(f"BNB Funder (0xb579...): {b_funder:.6f} BNB")
    
    # Check USDC balance of funder
    usdc_abi = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]
    contract = w3.eth.contract(address=Web3.to_checksum_address("0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d"), abi=usdc_abi)
    bal = contract.functions.balanceOf(Web3.to_checksum_address(funder)).call()
    print(f"USDC Funder (0xb579...): ${bal / 1e18:.4f} USDC")

if __name__ == "__main__":
    run_web3_transfer()
