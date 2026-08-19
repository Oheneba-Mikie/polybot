import requests
import json

def decode_txs():
    rpc_url = "https://polygon-bor-rpc.publicnode.com"
    txs = [
        ("Tx 1", "0xe8d29df88d771135b0b07ae4d11f4a35f95b36e24a6cd09a160a5b5fda1b1f24"),
        ("Tx 2", "0xbb77f4da17ae583a0000d1c81ff3f7d07cc604e2801034cff0a1cb795af9cf24")
    ]
    
    print("=== DECODING POLYGON TRANSACTIONS ===")
    for label, tx_hash in txs:
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getTransactionByHash",
            "params": [tx_hash],
            "id": 1
        }
        r = requests.post(rpc_url, json=payload).json()
        res = r.get("result")
        if res:
            from_addr = res.get("from")
            to_addr = res.get("to")
            data = res.get("input", "0x")
            print(f"\n{label} ({tx_hash[:16]}...):")
            print(f"  From: {from_addr}")
            print(f"  To:   {to_addr}")
            if len(data) >= 138:
                # ERC20 transfer(address _to, uint256 _value)
                recip = "0x" + data[34:74]
                amt_units = int(data[74:138], 16) / 1e6
                print(f"  ERC20 Recipient: {recip}")
                print(f"  ERC20 Amount:    ${amt_units:.4f} USDC")
        else:
            print(f"\n{label}: Transaction hash not found on Polygon mainnet yet.")

if __name__ == "__main__":
    decode_txs()
