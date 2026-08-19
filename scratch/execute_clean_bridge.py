import os, json, time, urllib.request
from dotenv import load_dotenv
from eth_account import Account
from eth_utils import to_checksum_address

load_dotenv()

def run_clean_bridge():
    pk = os.getenv("POLYMARKET_PRIVATE_KEY", "0x535a7ea810ec26c77dd75ed03798356c27cb70fcd283782e0411e0d896b56b3f")
    funder = to_checksum_address("0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8")
    
    print("=== EXECUTING AUTOMATED CROSS-CHAIN BRIDGE ===")
    
    rpc = "https://bsc-rpc.publicnode.com"
    token = to_checksum_address("0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d")
    
    # 1. Fetch Li.Fi Quote
    url = f"https://li.quest/v1/quote?fromChain=56&toChain=137&fromToken={token}&toToken=0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174&fromAddress={funder}&fromAmount=3310000000000000000"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    res = urllib.request.urlopen(req, timeout=15)
    quote = json.loads(res.read().decode('utf-8'))
    
    tx_req = quote["transactionRequest"]
    spender = to_checksum_address(tx_req["to"])
    
    # Set Nonce directly to 2
    nonce = 2
    print(f"Current Nonce: {nonce}")
    
    # Approve Li.Fi spender
    approve_data = f"0x095ea7b3{spender[2:].zfill(64)}ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    
    tx_approve = {
        'nonce': nonce,
        'gasPrice': 3000000000, # 3 Gwei
        'gas': 60000,
        'to': token,
        'value': 0,
        'data': bytes.fromhex(approve_data[2:]),
        'chainId': 56
    }
    
    signed_app = Account.sign_transaction(tx_approve, pk)
    payload = {"jsonrpc": "2.0", "method": "eth_sendRawTransaction", "params": ["0x" + signed_app.raw_transaction.hex()], "id": 2}
    req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    res_app = urllib.request.urlopen(req).read().decode('utf-8')
    print("Approve Tx Result:", res_app)
    
    time.sleep(4.0)
    
    # Send Bridge Tx
    tx_bridge = {
        'nonce': nonce + 1,
        'gasPrice': 3000000000, # 3 Gwei
        'gas': 300000,
        'to': spender,
        'value': int(tx_req.get("value", "0x0"), 16),
        'data': bytes.fromhex(tx_req["data"][2:]),
        'chainId': 56
    }
    
    signed_br = Account.sign_transaction(tx_bridge, pk)
    payload = {"jsonrpc": "2.0", "method": "eth_sendRawTransaction", "params": ["0x" + signed_br.raw_transaction.hex()], "id": 3}
    req = urllib.request.Request(rpc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    res_br = urllib.request.urlopen(req).read().decode('utf-8')
    print("Bridge Tx Result:", res_br)

if __name__ == "__main__":
    run_clean_bridge()
