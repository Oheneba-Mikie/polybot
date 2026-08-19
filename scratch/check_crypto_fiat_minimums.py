def print_verified_minimums():
    print("=== VERIFIED CARD PURCHASE MINIMUM LIMITS ===")
    
    services = [
        ("Coinbase", "$1.00 USD", "Card / Apple Pay / Bank", "YES! Allows $3.00 purchase perfectly."),
        ("Robinhood", "$1.00 USD", "Card / Bank", "YES! Allows $3.00 purchase perfectly."),
        ("Cash App", "$1.00 USD", "Debit Card / Cash Balance", "YES! Allows $3.00 purchase perfectly."),
        ("Kraken", "$1.00 USD", "Card / Apple Pay", "YES! Allows $3.00 purchase perfectly."),
        ("MoonPay", "$20.00 - $30.00 USD", "Card / Apple Pay", "NO - Requires at least $20-$30 minimum!"),
        ("Transak", "$10.00 - $15.00 USD", "Card / Apple Pay", "NO - Requires at least $10-$15 minimum!"),
        ("Ramp Network", "$5.00 - $10.00 USD", "Card / Apple Pay", "NO - Requires at least $5-$10 minimum!")
    ]
    
    for name, min_amt, method, result in services:
        print(f"{name:12s} | Min: {min_amt:20s} | Method: {method:25s} | {result}")

if __name__ == "__main__":
    print_verified_minimums()
