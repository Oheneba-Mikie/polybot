import os
import sys
import time
import json
import requests

# Force UTF-8 encoding on Windows console output to prevent charmap crashes
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath("latency_arb_railway_deploy"))
import app

def run_continuous_11min_simulation():
    print("=== CONTINUOUS 11-MINUTE LIVE ORDER BOOK SIMULATION (NO REAL MONEY) ===")
    print("Running for 660 seconds across active & upcoming 5-minute Polymarket windows...\n")
    
    start_time = time.time()
    duration = 660  # 11 minutes
    trades_simulated = 0
    total_cash_gained = 0.0
    total_cash_spent = 0.0

    current_slug = None

    while (time.time() - start_time) < duration:
        elapsed = time.time() - start_time
        rem = duration - elapsed
        
        # 1. Resolve current 5-minute market slug
        now_ts = int(time.time())
        w_s = (now_ts // 300) * 300
        slug = f"btc-updown-5m-{w_s}"
        
        if slug != current_slug:
            current_slug = slug
            print(f"\n--- NEW MARKET CYCLE: {slug} (Elapsed: {elapsed:.0f}s / {duration}s) ---")
            market = app.resolve_market_by_slug(slug)
            if market:
                print(f"[INFO] Resolved Token IDs -> UP: ...{market['up_id'][-8:]} | DOWN: ...{market['down_id'][-8:]}")
                app.book_feed.subscribe(market["up_id"], market["down_id"])
                time.sleep(1.5)

        # 2. Check live order book WebSocket stream
        prices = app.book_feed.latest()
        spot_btc = app.ws_feed.latest()[0] if app.ws_feed.latest() else 63000.0
        
        if prices:
            (u_a, u_b), (d_a, d_b) = prices
            print(f"[{elapsed:.0f}s / 660s] [SCANNING] Spot BTC: ${spot_btc:,.2f} | UP Ask: ${u_a:.2f}, Bid: ${u_b:.2f} | DN Ask: ${d_a:.2f}, Bid: ${d_b:.2f}")
            
            # 3. Simulate an entry test once per market cycle if UP ask is reasonably priced
            if trades_simulated < (int(elapsed // 180) + 1) and u_a is not None and 0.10 <= u_a <= 0.80:
                trades_simulated += 1
                entry_p = u_a
                cost = 5.0 * entry_p
                total_cash_spent += cost
                print(f"\n[SIMULATED ENTRY #{trades_simulated}] Bought 5.0 UP shares @ ${entry_p:.4f} (Cost: ${cost:.2f})")
                print(f"   Early Stop-Loss Threshold (60%): ${entry_p*0.60:.4f}")
                
                # Fetch live order book bid depth
                r = requests.get(f"https://clob.polymarket.com/book?token_id={market['up_id']}", timeout=5).json()
                bids = r.get("bids", [])
                sorted_bids = sorted(bids, key=lambda b: float(b["price"]), reverse=True)
                
                # Perform Descending Sweep
                print(f"   [DESCENDING SWEEP] Sweeping 5.0 shares across {len(sorted_bids)} live order book bid levels...")
                rem_shares = 5.0
                returned = 0.0
                sw_start = time.time()
                
                for idx, b in enumerate(sorted_bids):
                    if rem_shares <= 0: break
                    p = float(b["price"])
                    s = float(b["size"])
                    if p <= 0: continue
                    match = min(rem_shares, s)
                    cash = match * p
                    returned += cash
                    rem_shares -= match
                    print(f"      Step {idx+1}: Sold {match:.1f} shares @ top bid ${p:.4f} | Cash: +${cash:.2f} | Rem: {rem_shares:.1f}")

                total_cash_gained += returned
                sw_time = (time.time() - sw_start) * 1000.0
                pnl = returned - cost
                print(f"   [SWEEP COMPLETE] Execution: {sw_time:.2f}ms | Cash Returned: ${returned:.2f} | Trade PnL: ${pnl:+.2f}")

        time.sleep(10.0)

    print("\n=======================================================")
    print("=== CONTINUOUS 11-MINUTE SIMULATION FINAL RESULTS ===")
    print("=======================================================")
    print(f"Total Test Duration: {time.time() - start_time:.1f} seconds")
    print(f"Total Simulated Trades: {trades_simulated}")
    print(f"Total Cash Spent: ${total_cash_spent:.2f} USDC")
    print(f"Total Cash Returned: ${total_cash_gained:.2f} USDC")
    print(f"Net Simulation PnL: ${total_cash_gained - total_cash_spent:+.2f} USDC")
    print("Zero real funds were used. POLYMARKET_LIVE_TRADING = False.")
    print("=======================================================")

if __name__ == "__main__":
    run_continuous_11min_simulation()
