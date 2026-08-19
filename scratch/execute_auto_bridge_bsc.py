import os, json, time, urllib.request
from dotenv import load_dotenv
from eth_account import Account

load_dotenv()

def auto_bridge():
    pk = os.getenv("POLYMARKET_PRIVATE_KEY", "0x535a7ea810ec26c77dd75ed03798356c27cb70fcd283782e0411e0d896b56b3f")
    funder = "0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8"
    
    print("=== AUTOMATED MAX BRIDGE EXECUTOR (BSC -> POLYGON) ===")
    print(f"Monitoring address: {funder}")
    
    # Check BNB balance
    rpc_bsc = "https://bsc-rpc.publicnode.com"
    payload = {"jsonrpc": "2.0", "method": "eth_getBalance", "params": [funder, "latest"], "id": 1}
    req = urllib.request.Request(rpc_bsc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    
    res = urllib.request.urlopen(req, timeout=5)
    bnb_hex = json.loads(res.read().decode('utf-8')).get("result", "0x0")
    bnb_val = int(bnb_hex, 16) / 1e18
    print(f"Current BNB Balance: {bnb_val:.6f} BNB")
    
    if bnb_val < 0.0005:
        print("Waiting for BNB gas to arrive...")
        return
        
    print("BNB Gas Confirmed! Requesting Li.Fi Max Bridge Quote...")
    
    # Query Li.Fi Quote
    from_token = "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d"
    to_token = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    amount = "3310000000000000000" # 3.31 USDC
    
    url = f"https://li.quest/v1/quote?fromChain=56&toChain=137&fromToken={from_token}&toToken={to_token}&fromAddress={funder}&fromAmount={amount}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    res = urllib.request.urlopen(req, timeout=15)
    r_json = json.loads(res.read().decode('utf-8'))
    
    tx_data = r_json.get("transactionRequest", {})
    to_addr = tx_data.get("to")
    data_hex = tx_data.get("data")
    value = int(tx_data.get("value", "0x0"), 16)
    
    print(f"Li.Fi Bridge Transaction Target: {to_addr}")
    print(f"Executing automated bridge transaction...")
    
    # 1. Approve USDC to Li.Fi router
    # approve(address spender, uint256 value)
    spender = tx_data.get("to")
    approve_data = f"0x095ea7b3{spender[2:].zfill(64)}ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    
    # Get Nonce (use pending)
    payload = {"jsonrpc": "2.0", "method": "eth_getTransactionCount", "params": [funder, "pending"], "id": 2}
    req = urllib.request.Request(rpc_bsc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    next_nonce = int(json.loads(urllib.request.urlopen(req).read().decode('utf-8'))["result"], 16)
    if next_nonce < 2: next_nonce = 2
    print(f"Current BSC Nonce: {next_nonce}")
    
    # Set exact gas price (3 Gwei on BSC)
    gas_price_wei = 3000000000 # 3 Gwei
    
    from eth_utils import to_checksum_address
    
    tx1 = {
        'nonce': next_nonce,
        'gasPrice': gas_price_wei,
        'gas': 60000,
        'to': to_checksum_address(from_token),
        'value': 0,
        'data': bytes.fromhex(approve_data[2:]),
        'chainId': 56
    }
    signed1 = Account.sign_transaction(tx1, pk)
    payload = {"jsonrpc": "2.0", "method": "eth_sendRawTransaction", "params": ["0x" + signed1.raw_transaction.hex()], "id": 4}
    req = urllib.request.Request(rpc_bsc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    res1 = urllib.request.urlopen(req).read().decode('utf-8')
    print("USDC Approval Tx Result:", res1)
    
    time.sleep(3.0)
    
    # Check updated nonce for bridge tx
    payload = {"jsonrpc": "2.0", "method": "eth_getTransactionCount", "params": [funder, "latest"], "id": 5}
    req = urllib.request.Request(rpc_bsc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    bridge_nonce = int(json.loads(urllib.request.urlopen(req).read().decode('utf-8'))["result"], 16)
    
    tx2 = {
        'nonce': next_nonce + 1,
        'gasPrice': gas_price_wei,
        'gas': 200000,
        'to': to_checksum_address(to_addr),
        'value': value,
        'data': bytes.fromhex(data_hex[2:]),
        'chainId': 56
    }
    signed2 = Account.sign_transaction(tx2, pk)
    payload = {"jsonrpc": "2.0", "method": "eth_sendRawTransaction", "params": ["0x" + signed2.raw_transaction.hex()], "id": 6}
    req = urllib.request.Request(rpc_bsc, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    res2 = urllib.request.urlopen(req).read().decode('utf-8')
    print("SUCCESS! Bridge Tx Broadcast Result:", res2)

if __name__ == "__main__":
    auto_bridge()
