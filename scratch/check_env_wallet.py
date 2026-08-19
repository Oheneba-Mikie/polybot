import os

def check_env():
    pk = os.getenv("POLYMARKET_PK", "")
    print(f"=== CHECKING ENV PRIVATE KEY & WALLET ADDRESS ===")
    
    try:
        from eth_account import Account
        if pk:
            acc = Account.from_key(pk)
            print(f"Bot Wallet Address from POLYMARKET_PK: {acc.address}")
        else:
            print("No POLYMARKET_PK found in env.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_env()
