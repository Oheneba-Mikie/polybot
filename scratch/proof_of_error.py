import json

# Let's inspect the math of the 18:18:21 buy and 18:18:32 sell
bought_shares_on_chain = 5.628833 # exact fill on-chain
attempted_sell_shares = 5.630000   # rounded up to 2 decimals

print("="*80)
print("🔍 THE EXACT MATHEMATICAL PROOF OF THE 18:18:32 ERROR:")
print("="*80)
print(f"1. You bought with USDC and received : {bought_shares_on_chain:.6f} tokens (Raw: 5628833)")
print(f"2. When selling, code rounded up to  : {attempted_sell_shares:.6f} tokens (Raw: 5630000)")
print(f"3. Difference (Attempted Over-Sell)  : +{attempted_sell_shares - bought_shares_on_chain:.6f} tokens")
print(f"4. Polymarket CLOB Error Response    : balance: 5628833, order amount: 5630000")
print("="*80)
