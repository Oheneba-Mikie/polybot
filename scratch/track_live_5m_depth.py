import requests
import json
import time
from datetime import datetime, timezone

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

def get_live_or_upcoming_5m_btc():
    now = int(time.time())
    # 5-minute intervals:
    # 5m = 300s. Current 5m window starts at (now // 300) * 300
    current_window_start = (now // 300) * 300
    next_window_start = current_window_start + 300
    
    # Check slugs
    candidates = [
        f"btc-updown-5m-{current_window_start}",
        f"btc-updown-5m-{next_window_start}",
    ]
    
    for slug in candidates:
        url = f"{GAMMA_API}/events?slug={slug}"
        try:
            r = requests.get(url, timeout=5).json()
            if r and len(r) > 0:
                event = r[0]
                markets = event.get("markets", [])
                if markets:
                    m = markets[0]
                    clob_token_ids = json.loads(m.get("clobTokenIds", "[]"))
                    outcomes = json.loads(m.get("outcomes", "[]"))
                    if len(clob_token_ids) >= 2:
                        return {
                            "slug": slug,
                            "title": event.get("title", slug),
                            "window_start": int(slug.split("-")[-1]),
                            "window_end": int(slug.split("-")[-1]) + 300,
                            "up_token": clob_token_ids[0],
                            "down_token": clob_token_ids[1],
                            "outcomes": outcomes
                        }
        except Exception as e:
            pass
            
    # Fallback search
    url = f"{GAMMA_API}/events?limit=30&active=true&closed=false"
    r = requests.get(url, timeout=5).json()
    for ev in r:
        slug = ev.get("slug", "")
        if "btc-updown-5m" in slug:
            markets = ev.get("markets", [])
            if markets:
                m = markets[0]
                clob_token_ids = json.loads(m.get("clobTokenIds", "[]"))
                outcomes = json.loads(m.get("outcomes", "[]"))
                if len(clob_token_ids) >= 2:
                    ts = int(slug.split("-")[-1])
                    return {
                        "slug": slug,
                        "title": ev.get("title", slug),
                        "window_start": ts,
                        "window_end": ts + 300,
                        "up_token": clob_token_ids[0],
                        "down_token": clob_token_ids[1],
                        "outcomes": outcomes
                    }
    return None

def fetch_book(token_id):
    try:
        r = requests.get(f"{CLOB_API}/book?token_id={token_id}", timeout=2).json()
        bids = r.get("bids", [])
        asks = r.get("asks", [])
        best_bid = float(bids[0]["price"]) if bids else 0.0
        best_bid_size = float(bids[0]["size"]) if bids else 0.0
        best_ask = float(asks[0]["price"]) if asks else 1.0
        best_ask_size = float(asks[0]["size"]) if asks else 0.0
        return {
            "best_bid": best_bid,
            "best_bid_size": best_bid_size,
            "best_ask": best_ask,
            "best_ask_size": best_ask_size,
            "bids": bids,
            "asks": asks
        }
    except Exception as e:
        return None

def run_live_audit(duration_seconds=300):
    market_info = get_live_or_upcoming_5m_btc()
    if not market_info:
        print("Could not find active 5m BTC market.")
        return

    print("="*100)
    print(f"LIVE AUDIT TARGET: {market_info['slug']}")
    print(f"Title: {market_info['title']}")
    print(f"UP Token: {market_info['up_token']}")
    print(f"DOWN Token: {market_info['down_token']}")
    now = int(time.time())
    print(f"Window: Start {market_info['window_start']} ({datetime.fromtimestamp(market_info['window_start'], tz=timezone.utc).strftime('%H:%M:%S UTC')}) -> End {market_info['window_end']} ({datetime.fromtimestamp(market_info['window_end'], tz=timezone.utc).strftime('%H:%M:%S UTC')})")
    print(f"Current Time: {datetime.fromtimestamp(now, tz=timezone.utc).strftime('%H:%M:%S UTC')} (Time remaining: {market_info['window_end'] - now}s)")
    print("="*100)
    print("Starting continuous live polling (every 1s)... Tracking order book changes, available shares, and dry-up timing...")
    print()

    snapshots = []
    start_time = time.time()
    
    # State tracking
    last_state = None
    state_start_time = time.time()
    
    # We will log snapshots and track state persistence
    while time.time() - start_time < duration_seconds:
        loop_ts = time.time()
        now_utc = datetime.fromtimestamp(loop_ts, tz=timezone.utc).strftime("%H:%M:%S.%f")[:-3]
        time_left = market_info['window_end'] - int(loop_ts)
        
        up_book = fetch_book(market_info['up_token'])
        down_book = fetch_book(market_info['down_token'])
        
        if up_book and down_book:
            up_ask = up_book['best_ask']
            up_ask_sz = up_book['best_ask_size']
            up_bid = up_book['best_bid']
            up_bid_sz = up_book['best_bid_size']
            
            down_ask = down_book['best_ask']
            down_ask_sz = down_book['best_ask_size']
            down_bid = down_book['best_bid']
            down_bid_sz = down_book['best_bid_size']
            
            combined_ask = up_ask + down_ask
            matched_shares = min(up_ask_sz, down_ask_sz)
            
            state_key = (round(up_ask, 3), round(up_ask_sz, 1), round(down_ask, 3), round(down_ask_sz, 1))
            
            snapshots.append({
                "timestamp": now_utc,
                "epoch": loop_ts,
                "time_left_s": time_left,
                "up_ask": up_ask,
                "up_ask_sz": up_ask_sz,
                "up_bid": up_bid,
                "up_bid_sz": up_bid_sz,
                "down_ask": down_ask,
                "down_ask_sz": down_ask_sz,
                "down_bid": down_bid,
                "down_bid_sz": down_bid_sz,
                "combined_ask": combined_ask,
                "matched_shares": matched_shares,
                "state_key": state_key
            })
        
        time.sleep(1.0)
        
        if time_left < -10:
            print(f"Market window closed. Finalizing audit.")
            break

    # Analyze persistence / dry-up duration of each distinct state / mispricing
    print("\n" + "="*115)
    print(f"AUDIT RESULTS ACROSS {len(snapshots)} LIVE SNAPSHOTS ({market_info['slug']})")
    print("="*115)
    
    # Group contiguous states to measure exactly how long each price/size level stayed before being dried up / updated
    contiguous_events = []
    curr_event = None
    
    for s in snapshots:
        if curr_event is None:
            curr_event = {
                "start_time": s["timestamp"],
                "start_epoch": s["epoch"],
                "time_left": s["time_left_s"],
                "up_ask": s["up_ask"],
                "up_ask_sz": s["up_ask_sz"],
                "down_ask": s["down_ask"],
                "down_ask_sz": s["down_ask_sz"],
                "combined": s["combined_ask"],
                "matched": s["matched_shares"],
                "count": 1,
                "end_time": s["timestamp"],
                "end_epoch": s["epoch"]
            }
        else:
            if s["state_key"] == (round(curr_event["up_ask"], 3), round(curr_event["up_ask_sz"], 1), round(curr_event["down_ask"], 3), round(curr_event["down_ask_sz"], 1)):
                curr_event["count"] += 1
                curr_event["end_time"] = s["timestamp"]
                curr_event["end_epoch"] = s["epoch"]
            else:
                curr_event["duration_s"] = round(curr_event["end_epoch"] - curr_event["start_epoch"] + 1.0, 1)
                contiguous_events.append(curr_event)
                curr_event = {
                    "start_time": s["timestamp"],
                    "start_epoch": s["epoch"],
                    "time_left": s["time_left_s"],
                    "up_ask": s["up_ask"],
                    "up_ask_sz": s["up_ask_sz"],
                    "down_ask": s["down_ask"],
                    "down_ask_sz": s["down_ask_sz"],
                    "combined": s["combined_ask"],
                    "matched": s["matched_shares"],
                    "count": 1,
                    "end_time": s["timestamp"],
                    "end_epoch": s["epoch"]
                }
    if curr_event:
        curr_event["duration_s"] = round(curr_event["end_epoch"] - curr_event["start_epoch"] + 1.0, 1)
        contiguous_events.append(curr_event)

    # Print Table
    header = f"{'Timestamp (UTC)':<15} | {'Countdown':<10} | {'UP Ask (Shares)':<22} | {'DOWN Ask (Shares)':<24} | {'Combined':<9} | {'Matched Pairs':<14} | {'Time Dried Up / Duration':<25}"
    print(header)
    print("-" * len(header))
    
    for idx, ev in enumerate(contiguous_events):
        t_str = ev["start_time"].split(".")[0]
        cd_str = f"T-{ev['time_left']}s" if ev['time_left'] >= 0 else f"Closed"
        up_str = f"${ev['up_ask']:.3f} ({ev['up_ask_sz']:.1f} sh)"
        dn_str = f"${ev['down_ask']:.3f} ({ev['down_ask_sz']:.1f} sh)"
        comb_str = f"${ev['combined']:.3f}"
        match_str = f"{ev['matched']:.1f} sh"
        
        # Dry up status
        if idx == len(contiguous_events) - 1 and ev['time_left'] <= 0:
            dry_str = f"Did not dry up (Expired)"
        else:
            dry_str = f"Dried up in {ev['duration_s']}s"
            
        print(f"{t_str:<15} | {cd_str:<10} | {up_str:<22} | {dn_str:<24} | {comb_str:<9} | {match_str:<14} | {dry_str:<25}")

    # Also check if there were any CLOB trade executions during this window
    print("\n" + "="*115)
    print(f"CHECKING EXECUTED TRADES ON CLOB DURING THIS WINDOW...")
    print("="*115)
    try:
        r_trades = requests.get(f"{CLOB_API}/trades?market={market_info['up_token']}", timeout=5).json()
        print(f"UP Token Recent Trades: {len(r_trades)}")
        for tr in r_trades[:5]:
            print(f"  -> Match Time: {tr.get('timestamp')} | Side: {tr.get('side')} | Price: ${tr.get('price')} | Size: {tr.get('size')} sh")
    except Exception as e:
        print(f"Trade query note: {e}")

if __name__ == "__main__":
    import sys
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    run_live_audit(duration)
