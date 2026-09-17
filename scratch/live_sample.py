import requests
import json
import time
import sys
from datetime import datetime, timezone

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

def get_live_or_upcoming_5m_btc():
    now = int(time.time())
    current_window_start = (now // 300) * 300
    next_window_start = current_window_start + 300
    
    candidates = [
        f"btc-updown-5m-{current_window_start}",
        f"btc-updown-5m-{next_window_start}",
    ]
    
    for slug in candidates:
        try:
            r = requests.get(f"{GAMMA_API}/events?slug={slug}", timeout=5).json()
            if r and len(r) > 0:
                markets = r[0].get("markets", [])
                if markets:
                    m = markets[0]
                    clob_token_ids = json.loads(m.get("clobTokenIds", "[]"))
                    outcomes = json.loads(m.get("outcomes", "[]"))
                    if len(clob_token_ids) >= 2:
                        ts = int(slug.split("-")[-1])
                        return {
                            "slug": slug,
                            "title": r[0].get("title", slug),
                            "window_start": ts,
                            "window_end": ts + 300,
                            "up_token": clob_token_ids[0],
                            "down_token": clob_token_ids[1],
                            "outcomes": outcomes
                        }
        except Exception:
            pass
            
    # Fallback
    try:
        r = requests.get(f"{GAMMA_API}/events?limit=25&active=true&closed=false", timeout=5).json()
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
    except Exception:
        pass
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
        }
    except Exception:
        return None

def main():
    market = get_live_or_upcoming_5m_btc()
    if not market:
        print("No active 5m BTC market found.")
        return

    now = int(time.time())
    print("="*110, flush=True)
    print(f"LIVE 5-MINUTE BTC WINDOW: {market['slug']}", flush=True)
    print(f"Title: {market['title']}", flush=True)
    print(f"Window Start: {datetime.fromtimestamp(market['window_start'], tz=timezone.utc).strftime('%H:%M:%S UTC')} | Window End: {datetime.fromtimestamp(market['window_end'], tz=timezone.utc).strftime('%H:%M:%S UTC')}", flush=True)
    print(f"Current UTC Time: {datetime.fromtimestamp(now, tz=timezone.utc).strftime('%H:%M:%S UTC')} (Time left in candle: {market['window_end'] - now}s)", flush=True)
    print("="*110, flush=True)

    header = f"{'Timestamp (UTC)':<15} | {'Countdown':<10} | {'UP Ask (Shares)':<22} | {'DOWN Ask (Shares)':<24} | {'Combined':<9} | {'Matched Pairs':<14} | {'Time Dried Up / Duration':<25}"
    print(header, flush=True)
    print("-" * len(header), flush=True)

    # We will sample continuously for 45 seconds and group into distinct state transitions
    samples = []
    end_poll = time.time() + 45

    while time.time() < end_poll:
        t_now = time.time()
        time_str = datetime.fromtimestamp(t_now, tz=timezone.utc).strftime("%H:%M:%S")
        time_left = market['window_end'] - int(t_now)
        
        up_b = fetch_book(market['up_token'])
        dn_b = fetch_book(market['down_token'])
        
        if up_b and dn_b:
            samples.append({
                "time_str": time_str,
                "epoch": t_now,
                "time_left": time_left,
                "up_ask": up_b["best_ask"],
                "up_ask_sz": up_b["best_ask_size"],
                "dn_ask": dn_b["best_ask"],
                "dn_ask_sz": dn_b["best_ask_size"],
                "combined": up_b["best_ask"] + dn_b["best_ask"],
                "matched": min(up_b["best_ask_size"], dn_b["best_ask_size"]),
                "key": (round(up_b["best_ask"], 3), round(up_b["best_ask_size"], 1), round(dn_b["best_ask"], 3), round(dn_b["best_ask_size"], 1))
            })
        time.sleep(0.8)

    # Group into contiguous events to show duration and dry-up timing
    events = []
    curr = None
    for s in samples:
        if curr is None:
            curr = dict(s)
            curr["count"] = 1
            curr["end_epoch"] = s["epoch"]
        elif s["key"] == curr["key"]:
            curr["count"] += 1
            curr["end_epoch"] = s["epoch"]
        else:
            curr["duration_s"] = round(curr["end_epoch"] - curr["epoch"] + 0.8, 1)
            events.append(curr)
            curr = dict(s)
            curr["count"] = 1
            curr["end_epoch"] = s["epoch"]
            
    if curr:
        curr["duration_s"] = round(curr["end_epoch"] - curr["epoch"] + 0.8, 1)
        curr["is_last"] = True
        events.append(curr)

    for i, ev in enumerate(events):
        cd_str = f"T-{ev['time_left']}s" if ev['time_left'] >= 0 else "Closed"
        up_str = f"${ev['up_ask']:.3f} ({ev['up_ask_sz']:.1f} sh)"
        dn_str = f"${ev['dn_ask']:.3f} ({ev['dn_ask_sz']:.1f} sh)"
        comb_str = f"${ev['combined']:.3f}"
        match_str = f"{ev['matched']:.1f} sh"
        
        if ev.get("is_last"):
            dry_str = f"Still open / persisting ({ev['duration_s']}s so far)"
        else:
            dry_str = f"Dried up in {ev['duration_s']}s"
            
        print(f"{ev['time_str']:<15} | {cd_str:<10} | {up_str:<22} | {dn_str:<24} | {comb_str:<9} | {match_str:<14} | {dry_str:<25}", flush=True)

if __name__ == "__main__":
    main()
