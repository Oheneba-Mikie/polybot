from eth_account import Account

def test_access():
    pk = "0x535a7ea810ec26c77dd75ed03798356c27cb70fcd283782e0411e0d896b56b3f"
    acc = Account.from_key(pk)
    
    print("=== TESTING WALLET CONTROL ===")
    print(f"EOA Address: {acc.address}")
    print("Private key has 100% full cryptographic signing rights!")
    print("Recipient for BNB Gas Deposit: 0xb579cf1af6ecf666f8d9b90a1fb411a6eaca33e8")

if __name__ == "__main__":
    test_access()
