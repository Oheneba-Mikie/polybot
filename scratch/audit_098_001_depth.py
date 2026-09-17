import requests
import json
import time
import datetime
import sys
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST = "https://clob.polymarket.com"
DATA_HOST = "https://data-api.polymarket.com"

def fetch_book(token_id):
    try:
        r = requests.get(f"{CLOB_HOST}/book?token_id={token_id}", timeout=3).json()
        bids = r.get("bids", [])
        asks = r.get("asks", [])
        return bids, asks
    except Exception:
        return [], []

def check_crypto_5m():
    print("\n" + "="*80)
    print("1. LIVE 5-MINUTE CRYPTO MARKETS (BTC / ETH / SOL)")
    print("="*80)
    now = int(time.time())
    cur_w = (now // 300) * 300
    
    # Check current window and previous window
    for w in [cur_w, cur_w - 300]:
        for coin in ["btc", "eth", "sol"]:
            slug = f"{coin}-updown-5m-{w}"
            try:
                r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
                if not r or not r[0].get("markets"):
                    continue
                m = r[0]["markets"][0]
                tokens = json.loads(m.get("clobTokenIds", "[]"))
                outcomes = json.loads(m.get("outcomes", "[]"))
                if len(tokens) < 2:
                    continue

                bids1, asks1 = fetch_book(tokens[0])
                bids2, asks2 = fetch_book(tokens[1])

                best_ask1 = float(min(asks1, key=lambda x: float(x["price"]))["price"]) if asks1 else None
                best_bid1 = float(max(bids1, key=lambda x: float(x["price"]))["price"]) if bids1 else None
                best_ask2 = float(min(asks2, key=lambda x: float(x["price"]))["price"]) if asks2 else None
                best_bid2 = float(max(bids2, key=lambda x: float(x["price"]))["price"]) if bids2 else None

                t_rem = (w + 300) - now
                status = f"LIVE (T-{t_rem}s)" if t_rem > 0 else "CLOSED"
                print(f"\nMarket: {slug} [{status}]")
                print(f"  {outcomes[0]}: Best Bid = {best_bid1} | Best Ask = {best_ask1}")
                print(f"  {outcomes[1]}: Best Bid = {best_bid2} | Best Ask = {best_ask2}")
                if best_ask1 and best_ask2:
                    print(f"  Combined Ask Cost: ${best_ask1 + best_ask2:.3f}")

                # Print asks and bids for each
                print(f"  Top Asks {outcomes[0]}: {[(round(float(a['price']),3), round(float(a['size']),1)) for a in asks1[:4]]}")
                print(f"  Top Asks {outcomes[1]}: {[(round(float(a['price']),3), round(float(a['size']),1)) for a in asks2[:4]]}")
            except Exception as e:
                pass

def check_general_extreme_books():
    print("\n" + "="*80)
    print("2. SCANNING MARKETS WITH OUTCOMES AT 0.95 - 0.99 (AND 0.01 - 0.05)")
    print("="*80)
    try:
        r = requests.get(f"{GAMMA_HOST}/markets?limit=100&closed=false&active=true", timeout=5).json()
    except Exception as e:
        print(f"Failed: {e}")
        return

    candidate_markets = []
    for m in r:
        try:
            tokens = json.loads(m.get("clobTokenIds", "[]"))
            prices = json.loads(m.get("outcomePrices", "[]"))
            outcomes = json.loads(m.get("outcomes", "[]"))
            if len(tokens) >= 2 and prices:
                p0 = float(prices[0])
                p1 = float(prices[1])
                if p0 >= 0.94 or p1 >= 0.94 or p0 <= 0.06 or p1 <= 0.06:
                    candidate_markets.append((m, tokens, outcomes, prices))
        except Exception:
            pass

    print(f"Found {len(candidate_markets)} active markets near price boundaries.")

    def inspect_candidate(item):
        m, tokens, outcomes, prices = item
        bids1, asks1 = fetch_book(tokens[0])
        bids2, asks2 = fetch_book(tokens[1])
        return m, tokens, outcomes, prices, bids1, asks1, bids2, asks2

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(inspect_candidate, candidate_markets[:15]))

    for m, tokens, outcomes, prices, bids1, asks1, bids2, asks2 in results:
        best_ask1 = float(min(asks1, key=lambda x: float(x["price"]))["price"]) if asks1 else None
        best_ask2 = float(min(asks2, key=lambda x: float(x["price"]))["price"]) if asks2 else None
        best_bid1 = float(max(bids1, key=lambda x: float(x["price"]))["price"]) if bids1 else None
        best_bid2 = float(max(bids2, key=lambda x: float(x["price"]))["price"]) if bids2 else None

        q = m.get("question", m.get("slug"))
        print(f"\nMarket: {q[:75]}")
        out0 = outcomes[0] if len(outcomes) > 0 else "Out 0"
        out1 = outcomes[1] if len(outcomes) > 1 else "Out 1"
        print(f"  {out0} (Price ~{prices[0]}): Bid={best_bid1} | Ask={best_ask1}")
        print(f"  {out1} (Price ~{prices[1]}): Bid={best_bid2} | Ask={best_ask2}")

        # Check asks at 0.98, 0.99
        all_asks = [(out0, asks1), (out1, asks2)]
        all_bids = [(out0, bids1), (out1, bids2)]
        
        for name, asks in all_asks:
            sh_98 = sum(float(a["size"]) for a in asks if 0.975 <= float(a["price"]) <= 0.985)
            sh_99 = sum(float(a["size"]) for a in asks if 0.985 < float(a["price"]) <= 0.995)
            sh_01 = sum(float(a["size"]) for a in asks if float(a["price"]) <= 0.015)
            sh_02 = sum(float(a["size"]) for a in asks if 0.015 < float(a["price"]) <= 0.025)
            if sh_98 > 0 or sh_99 > 0 or sh_01 > 0 or sh_02 > 0:
                print(f"    -> {name} ASKS: @ 0.98: {sh_98:,.0f} sh | @ 0.99: {sh_99:,.0f} sh | @ 0.01: {sh_01:,.0f} sh | @ 0.02: {sh_02:,.0f} sh")

        for name, bids in all_bids:
            sh_bid_01 = sum(float(b["size"]) for b in bids if float(b["price"]) <= 0.015)
            if sh_bid_01 > 0:
                print(f"    -> {name} BIDS (people wanting to buy at 1c): {sh_bid_01:,.0f} sh")

def audit_historical_trades():
    print("\n" + "="*80)
    print("3. HISTORICAL TRADES IN FAST VOLATILITY (PAST 24H)")
    print("="*80)
    # Check 10 recent 5-min markets that completed
    now = int(time.time())
    cur_w = (now // 300) * 300
    past_windows = [cur_w - (i * 300) for i in range(1, 15)]

    total_98_buys = 0
    total_98_vol = 0
    total_99_buys = 0
    total_99_vol = 0
    total_01_buys = 0
    total_01_vol = 0
    total_02_buys = 0
    total_02_vol = 0

    checked_markets = 0

    for w in past_windows:
        slug = f"btc-updown-5m-{w}"
        try:
            r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
            if not r or not r[0].get("markets"):
                continue
            m = r[0]["markets"][0]
            cid = m.get("conditionId")
            if not cid:
                continue

            trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=1000", timeout=3).json()
            if not isinstance(trades, list) or not trades:
                continue

            checked_markets += 1
            for t in trades:
                side = str(t.get("side", "")).upper()
                px = float(t.get("price", 0))
                sz = float(t.get("size", 0))

                if side == "BUY":
                    if 0.975 <= px <= 0.985:
                        total_98_buys += 1
                        total_98_vol += sz
                    elif 0.985 < px <= 0.995:
                        total_99_buys += 1
                        total_99_vol += sz
                    elif px <= 0.015:
                        total_01_buys += 1
                        total_01_vol += sz
                    elif 0.015 < px <= 0.025:
                        total_02_buys += 1
                        total_02_vol += sz
        except Exception:
            pass

    print(f"Audited {checked_markets} closed 5-minute Bitcoin markets:")
    print(f"  • BUY trades filled at $0.98: {total_98_buys} trades | Total shares filled: {total_98_vol:,.0f} sh (Avg per market: {total_98_vol/max(1,checked_markets):,.0f} sh)")
    print(f"  • BUY trades filled at $0.99: {total_99_buys} trades | Total shares filled: {total_99_vol:,.0f} sh (Avg per market: {total_99_vol/max(1,checked_markets):,.0f} sh)")
    print(f"  • BUY trades filled at $0.01: {total_01_buys} trades | Total shares filled: {total_01_vol:,.0f} sh (Avg per market: {total_01_vol/max(1,checked_markets):,.0f} sh)")
    print(f"  • BUY trades filled at $0.02: {total_02_buys} trades | Total shares filled: {total_02_vol:,.0f} sh (Avg per market: {total_02_vol/max(1,checked_markets):,.0f} sh)")

if __name__ == "__main__":
    check_crypto_5m()
    check_general_extreme_books()
    audit_historical_trades()
