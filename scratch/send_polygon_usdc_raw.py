import os, json, urllib.request
from dotenv import load_dotenv
from eth_account import Account

load_dotenv()

def transfer_raw():
    pk = os.getenv("POLYMARKET_PRIVATE_KEY", "0x535a7ea810ec26c77dd75ed03798356c27cb70fcd283782e0411e0d896b56b3f")
    funder = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    recipient = "0x4cd00e387622c35bddb9b4c962c136462338bc31" # Binance Deposit Address
    amount_usdc = 0.70 # $0.70 USDC
    
    print(f"=== TRANSFERRING ${amount_usdc:.2f} USDC FROM POLYMARKET TO BINANCE ===")
    
    rpc = "https://polygon-bor-rpc.publicnode.com"
    usdc_contract = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    
    # 1. Get Nonce
    payload = {"jsonrpc": "2.0", "method": "eth_getTransactionCount", "params": [funder, "latest"], "id": 1}
    req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    res = urllib.request.urlopen(req, timeout=5)
    nonce = int(json.loads(res.read().decode('utf-8'))["result"], 16)
    
    # 2. Get Gas Price
    payload = {"jsonrpc": "2.0", "method": "eth_gasPrice", "params": [], "id": 2}
    req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    res = urllib.request.urlopen(req, timeout=5)
    gas_price = int(json.loads(res.read().decode('utf-8'))["result"], 16)
    
    # 3. Build Transfer Data: transfer(address,uint256) signature = 0xa9059cbb
    addr_padded = recipient[2:].zfill(64)
    amount_hex = hex(int(amount_usdc * 1e6))[2:].zfill(64)
    data_hex = f"a9059cbb{addr_padded}{amount_hex}"
    
    # 4. Build & Sign Transaction
    tx_dict = {
        'nonce': nonce,
        'gasPrice': gas_price,
        'gas': 100000,
        'to': usdc_contract,
        'value': 0,
        'data': bytes.fromhex(data_hex),
        'chainId': 137
    }
    
    signed_tx = Account.sign_transaction(tx_dict, pk)
    raw_tx_hex = "0x" + signed_tx.raw_transaction.hex()
    
    # 5. Broadcast Raw Transaction
    payload = {"jsonrpc": "2.0", "method": "eth_sendRawTransaction", "params": [raw_tx_hex], "id": 3}
    req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    res = urllib.request.urlopen(req, timeout=5)
    out = json.loads(res.read().decode('utf-8'))
    print("Send Tx Result:", out)

if __name__ == "__main__":
    transfer_raw()
