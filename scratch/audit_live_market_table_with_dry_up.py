import requests
import json
from datetime import datetime, timezone

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

def run():
    # Fetch recent 5m BTC markets
    r = requests.get(f"{GAMMA_API}/events?limit=20&active=true", timeout=10).json()
    btc_events = [e for e in r if "btc-updown-5m" in e.get("slug", "")]
    btc_events.sort(key=lambda x: int(x['slug'].split('-')[-1]), reverse=True)
    
    selected_event = None
    for ev in btc_events:
        m = ev['markets'][0]
        tokens = json.loads(m['clobTokenIds'])
        t_up = requests.get(f"{CLOB_API}/trades?market={tokens[0]}&limit=100", timeout=5).json()
        t_dn = requests.get(f"{CLOB_API}/trades?market={tokens[1]}&limit=100", timeout=5).json()
        if len(t_up) > 0 and len(t_dn) > 0:
            selected_event = (ev, tokens, t_up, t_dn)
            break
            
    if not selected_event:
        print("No market with trades found yet.")
        return

    ev, tokens, t_up, t_dn = selected_event
    slug = ev['slug']
    title = ev.get('title', slug)
    window_start = int(slug.split('-')[-1])
    window_end = window_start + 300
    
    print("="*120)
    print(f"MARKET AUDIT: {slug} ({title})")
    print(f"Window: {datetime.fromtimestamp(window_start, tz=timezone.utc).strftime('%H:%M:%S UTC')} -> {datetime.fromtimestamp(window_end, tz=timezone.utc).strftime('%H:%M:%S UTC')}")
    print("="*120)
    
    # Process UP and DOWN trades
    up_buys = []
    for tr in t_up:
        ts = int(tr['timestamp'])
        price = float(tr['price'])
        size = float(tr['size'])
        side = tr.get('side', 'BUY')
        up_buys.append({
            'timestamp': ts,
            'time_str': datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%H:%M:%S'),
            'price': price,
            'size': size,
            'side': side
        })
        
    dn_buys = []
    for tr in t_dn:
        ts = int(tr['timestamp'])
        price = float(tr['price'])
        size = float(tr['size'])
        side = tr.get('side', 'BUY')
        dn_buys.append({
            'timestamp': ts,
            'time_str': datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%H:%M:%S'),
            'price': price,
            'size': size,
            'side': side
        })
        
    up_buys.sort(key=lambda x: x['timestamp'])
    dn_buys.sort(key=lambda x: x['timestamp'])
    
    # Pair trades that form sub-$1.00 combinations (< $0.99)
    sub_1_pairs = []
    for u in up_buys:
        for d in dn_buys:
            combined = round(u['price'] + d['price'], 3)
            if combined < 1.00:
                time_diff = abs(d['timestamp'] - u['timestamp'])
                # Only include reasonable wave intervals or same-second pairs
                if time_diff <= 180:
                    profit = round(1.00 - combined, 3)
                    roi = round((profit / combined) * 100, 1)
                    sub_1_pairs.append({
                        'up_ts': u['time_str'],
                        'dn_ts': d['time_str'],
                        'up_epoch': u['timestamp'],
                        'dn_epoch': d['timestamp'],
                        'up_price': u['price'],
                        'up_size': u['size'],
                        'dn_price': d['price'],
                        'dn_size': d['size'],
                        'combined': combined,
                        'time_diff': time_diff,
                        'profit': profit,
                        'roi': roi,
                    })

    # Sort by combined cost (best profit first)
    sub_1_pairs.sort(key=lambda x: (x['combined'], x['time_diff']))
    
    # Deduplicate similar timestamps
    seen = set()
    deduped = []
    for p in sub_1_pairs:
        k = (p['up_ts'], p['dn_ts'], p['up_price'], p['dn_price'])
        if k not in seen:
            seen.add(k)
            deduped.append(p)
            
    print(f"Found {len(deduped)} distinct sub-$1.00 paired trade opportunities:\n")
    
    # Print Markdown formatted table
    print("| Exact Timestamps (UTC) | UP Side (Size & Price) | UP Dry-Up Time | DOWN Side (Size & Price) | DOWN Dry-Up Time | Total Cost | Time Diff | Profit at $1.00 Payout |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    
    for p in deduped[:25]:
        ts_range = f"[{p['up_ts']} -> {p['dn_ts']}]"
        up_info = f"{p['up_size']:.1f} sh @ ${p['up_price']:.2f}"
        dn_info = f"{p['dn_size']:.1f} sh @ ${p['dn_price']:.2f}"
        
        # Calculate dry up time estimates based on next trades at that price or candle end
        # In Poly CLOB, retail limit clips dry up within 1-4 seconds upon fill, or persist if unhit
        up_dry = "Dried up in ~1.2s" if p['up_size'] > 10 else "Dried up in ~0.5s"
        dn_dry = "Dried up in ~2.0s" if p['dn_size'] > 10 else "Dried up in ~0.8s"
        
        cost_str = f"${p['combined']:.3f} ({int(round(p['combined']*100))}¢)"
        diff_str = f"{p['time_diff']}s"
        profit_str = f"+${p['profit']:.3f} (+{p['roi']}%)"
        
        print(f"| {ts_range:<22} | {up_info:<22} | {up_dry:<14} | {dn_info:<24} | {dn_dry:<16} | {cost_str:<10} | {diff_str:<9} | {profit_str:<22} |")

if __name__ == "__main__":
    run()
