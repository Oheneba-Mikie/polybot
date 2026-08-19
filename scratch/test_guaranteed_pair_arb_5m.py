import requests
import json
import time

def test_5m_pair_arb():
    print("=== TESTING 5-MINUTE LATE-ROUND PAIR ARBITRAGE ENGINE ===")
    
    # Calculate current 5m cycle end timestamp
    now_ts = int(time.time())
    current_5m_end = ((now_ts // 300) + 1) * 300
    slug = f"btc-updown-5m-{current_5m_end}"
    
    rem_secs = current_5m_end - now_ts
    print(f"Current Market Slug: {slug}")
    print(f"Seconds Remaining in Cycle: {rem_secs}s")
    
    url = f"https://gamma-api.polymarket.com/events?slug={slug}"
    r = requests.get(url).json()
    
    if not r or len(r) == 0:
        print("Market loading from Gamma...")
        return
        
    mkt = r[0]["markets"][0]
    clob_tokens = json.loads(mkt.get("clobTokenIds", "[]"))
    up_id, down_id = clob_tokens[0], clob_tokens[1]
    
    r_up = requests.get(f"https://clob.polymarket.com/book?token_id={up_id}").json()
    r_dn = requests.get(f"https://clob.polymarket.com/book?token_id={down_id}").json()
    
    up_asks = r_up.get("asks", [])
    dn_asks = r_dn.get("asks", [])
    
    up_ask = float(up_asks[0]["price"]) if up_asks else 1.0
    dn_ask = float(dn_asks[0]["price"]) if dn_asks else 1.0
    
    pair_cost = up_ask + dn_ask
    print(f"\nTop Ask UP:   ${up_ask:.4f}")
    print(f"Top Ask DOWN: ${dn_ask:.4f}")
    print(f"COMBINED PAIR COST: ${pair_cost:.4f}")
    
    MAX_PAIR_COST = 0.98
    if pair_cost <= MAX_PAIR_COST:
        profit_per_pair = 1.00 - pair_cost
        roi = (profit_per_pair / pair_cost) * 100
        print(f"\n🎉 [GUARANTEED PAIR ARB DETECTED!] Pair Cost ${pair_cost:.4f} <= ${MAX_PAIR_COST:.2f}")
        print(f"   Guaranteed Profit per Pair: +${profit_per_pair:.4f} (+{roi:.2f}% Risk-Free ROI)")
    else:
        diff_cents = (pair_cost - MAX_PAIR_COST) * 100
        print(f"\nScanning: Pair Cost (${pair_cost:.4f}) > Max Budget (${MAX_PAIR_COST:.2f}). Waiting for {diff_cents:.1f}c spread convergence...")

if __name__ == "__main__":
    test_5m_pair_arb()
