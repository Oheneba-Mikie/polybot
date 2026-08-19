import os, json, urllib.request
from dotenv import load_dotenv
from eth_account import Account
from eth_utils import to_checksum_address

load_dotenv()

def transfer_bsc_usdc():
    pk = os.getenv("POLYMARKET_PRIVATE_KEY", "0x535a7ea810ec26c77dd75ed03798356c27cb70fcd283782e0411e0d896b56b3f")
    funder = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    recipient = "0x0159010e49e7Db204a897819a787f41CFe1F2C67" # Account 1
    token = "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d" # BSC-USD
    
    print(f"=== TRANSFERRING $3.31 USDC FROM {funder} TO {recipient} ON BSC ===")
    
    rpc = "https://bsc-rpc.publicnode.com"
    
    nonce = 2
    print(f"Current Nonce: {nonce}")
    
    # transfer(address to, uint256 value) -> 0xa9059cbb
    addr_padded = recipient[2:].zfill(64)
    amount_hex = hex(int(3.31 * 1e18))[2:].zfill(64)
    data = f"a9059cbb{addr_padded}{amount_hex}"
    
    tx = {
        'nonce': nonce,
        'gasPrice': 3000000000, # 3 Gwei
        'gas': 60000,
        'to': to_checksum_address(token),
        'value': 0,
        'data': bytes.fromhex(data),
        'chainId': 56
    }
    
    signed = Account.sign_transaction(tx, pk)
    raw_tx = "0x" + signed.raw_transaction.hex()
    
    payload = {"jsonrpc": "2.0", "method": "eth_sendRawTransaction", "params": [raw_tx], "id": 2}
    req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    res = urllib.request.urlopen(req, timeout=5)
    out = json.loads(res.read().decode('utf-8'))
    print("Transfer Result:", out)

if __name__ == "__main__":
    transfer_bsc_usdc()
