from eth_account import Account

pk = "0x535a7ea810ec26c77dd75ed03798356c27cb70fcd283782e0411e0d896b56b3f"
acc = Account.from_key(pk)
print(f"=== EXACT DERIVED ADDRESS FOR PRIVATE KEY ===")
print(f"Address: {acc.address}")
