import requests
import json
import time
import datetime
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

# 1. Audit previous candle 10:45-10:50 AM ET (btc-updown-5m-1789224300)
# 2. Audit current active candle 10:55-11:00 AM ET (btc-updown-5m-1789224900)

now = int(time.time())
w_cur = (now // 300) * 300
w_prev = 1789224300 # 10:45 AM ET

print("="*110, flush=True)
print("📊 DETAILED ORDER BOOK SHARE DEPTH AUDIT: CAN YOUR BOT BUY THESE SHARES?", flush=True)
print("="*110, flush=True)

for label, ts in [("PAST CANDLE (10:45 AM - 10:50 AM ET)", w_prev), ("ACTIVE LIVE CANDLE RIGHT NOW", w_cur)]:
    slug = f"btc-updown-5m-{ts}"
    print(f"\n📌 {label}: {slug}", flush=True)
    print("-" * 110, flush=True)
    
    r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
    if not r or not r[0].get("markets"):
        print("Market not found")
        continue
        
    mkt = r[0]["markets"][0]
    cid = mkt.get("conditionId")
    tokens = json.loads(mkt.get("clobTokenIds", "[]"))
    outcomes = json.loads(mkt.get("outcomes", "[]"))
    
    up_token = tokens[0] if len(tokens) > 0 else None
    dn_token = tokens[1] if len(tokens) > 1 else None
    if len(outcomes) >= 2 and outcomes[0].lower() not in ("up", "yes"):
        up_token, dn_token = tokens[1], tokens[0]
        
    # If active, fetch live order book depth across all levels
    if up_token and dn_token:
        r_up = requests.get(f"{CLOB_HOST}/book?token_id={up_token}", timeout=3).json()
        r_dn = requests.get(f"{CLOB_HOST}/book?token_id={dn_token}", timeout=3).json()
        
        u_asks = sorted(r_up.get("asks", []), key=lambda x: float(x["price"]))
        d_asks = sorted(r_dn.get("asks", []), key=lambda x: float(x["price"]))
        
        print(f"\n  📖 CURRENT LIVE ORDER BOOK ASKS (Shares You Can Instantly Buy Right Now):", flush=True)
        print(f"     {'UP Tokens for Sale':<45} | {'DOWN Tokens for Sale':<45}")
        print(f"     {'-'*45} | {'-'*45}")
        
        max_rows = max(len(u_asks[:5]), len(d_asks[:5]))
        for i in range(max_rows):
            u_str = f"Level {i+1}: {float(u_asks[i]['size']):>7.1f} sh @ ${float(u_asks[i]['price']):.3f} (Cost: ${float(u_asks[i]['size'])*float(u_asks[i]['price']):>6.2f})" if i < len(u_asks) else "-"
            d_str = f"Level {i+1}: {float(d_asks[i]['size']):>7.1f} sh @ ${float(d_asks[i]['price']):.3f} (Cost: ${float(d_asks[i]['size'])*float(d_asks[i]['price']):>6.2f})" if i < len(d_asks) else "-"
            print(f"     {u_str:<45} | {d_str:<45}", flush=True)
            
    # Also fetch all actual public fills from the candle to show trade sizes
    r_tr = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=100", timeout=3).json()
    if r_tr:
        trade_sizes = [float(t.get("size", 0)) for t in r_tr]
        up_trades = [t for t in r_tr if str(t.get("outcome", "")).upper() in ("UP", "YES")]
        dn_trades = [t for t in r_tr if str(t.get("outcome", "")).upper() in ("DOWN", "NO")]
        
        print(f"\n  📊 REAL TRADE EXECUTION SIZES FILLED BY BUYERS ON THIS CANDLE:", flush=True)
        print(f"     • Average Trade Size: {sum(trade_sizes)/max(1, len(trade_sizes)):.1f} shares")
        print(f"     • Largest Single Trade: {max(trade_sizes):.1f} shares ($ {max(trade_sizes)*0.5:.2f}+)")
        print(f"     • Smallest Single Trade: {min(trade_sizes):.1f} shares")
        print(f"     • Total UP Shares Bought:   {sum(float(t.get('size', 0)) for t in up_trades):.1f} shares")
        print(f"     • Total DOWN Shares Bought: {sum(float(t.get('size', 0)) for t in dn_trades):.1f} shares")
        
        print(f"\n     Recent Fills Showing Real Buyer Quantities:", flush=True)
        for t in r_tr[:8]:
            out = str(t.get("outcome", "")).upper()
            sz = float(t.get("size", 0))
            px = float(t.get("price", 0))
            cost = sz * px
            print(f"       • Buyer Bought {sz:>7.2f} {out:<4} shares @ ${px:.3f} (Total Fill Cost = ${cost:.2f})", flush=True)

print("\n" + "="*110, flush=True)
