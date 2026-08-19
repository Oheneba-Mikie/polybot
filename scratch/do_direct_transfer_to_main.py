import os, json, urllib.request
from dotenv import load_dotenv
from eth_account import Account
from eth_utils import to_checksum_address

load_dotenv()

def do_transfer():
    pk = os.getenv("POLYMARKET_PRIVATE_KEY", "0x535a7ea810ec26c77dd75ed03798356c27cb70fcd283782e0411e0d896b56b3f")
    funder = to_checksum_address("0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8")
    recipient = to_checksum_address("0x0159010e49e7Db204a897819a787f41CFe1F2C67") # Account 1
    token = to_checksum_address("0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d")
    
    print(f"=== DIRECT BEP20 TRANSFER OF $3.31 USDC FROM {funder} TO {recipient} ===")
    
    rpc = "https://bsc-rpc.publicnode.com"
    
    # Nonce 2
    nonce = 2
    
    # 3.31 USDC (18 decimals) = 3310000000000000000
    addr_padded = recipient[2:].zfill(64)
    amount_hex = hex(3310000000000000000)[2:].zfill(64)
    data = f"a9059cbb{addr_padded}{amount_hex}"
    
    tx = {
        'nonce': nonce,
        'gasPrice': 1000000000, # 1 Gwei
        'gas': 40000,
        'to': token,
        'value': 0,
        'data': bytes.fromhex(data),
        'chainId': 56
    }
    
    signed = Account.sign_transaction(tx, pk)
    raw_tx = "0x" + signed.raw_transaction.hex()
    
    payload = {"jsonrpc": "2.0", "method": "eth_sendRawTransaction", "params": [raw_tx], "id": 1}
    req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    res = urllib.request.urlopen(req, timeout=10)
    out = json.loads(res.read().decode('utf-8'))
    print("Direct Transfer Tx Result:", out)

if __name__ == "__main__":
    do_transfer()
