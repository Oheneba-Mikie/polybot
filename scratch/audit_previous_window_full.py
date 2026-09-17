import requests
import json
import time
import datetime
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

GAMMA_HOST = "https://gamma-api.polymarket.com"

now = int(time.time())
cur_w = (now // 300) * 300
prev_w = cur_w - 300 # The 5m window that just finished (04:40 - 04:45 UTC)

slug = f"btc-updown-5m-{prev_w}"
print(f"=== COMPREHENSIVE BOOK & TRADE AUDIT FOR FINISHED 5M MARKET: {slug} ===")
print(f"Window Time: {datetime.datetime.fromtimestamp(prev_w, tz=datetime.timezone.utc).strftime('%H:%M:%S')} - {datetime.datetime.fromtimestamp(prev_w + 300, tz=datetime.timezone.utc).strftime('%H:%M:%S')} UTC\n")

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=5).json()
if not r or not r[0].get("markets"):
    print("Could not fetch market data for", slug)
    exit(1)

m = r[0]["markets"][0]
tokens = json.loads(m.get("clobTokenIds", "[]"))
up_token, dn_token = tokens[0], tokens[1]

# Fetch all trades executed during this window
r_up = requests.get(f"https://data-api.polymarket.com/trades?asset={up_token}&limit=500", timeout=5).json()
r_dn = requests.get(f"https://data-api.polymarket.com/trades?asset={dn_token}&limit=500", timeout=5).json()

trades_up = [t for t in (r_up if isinstance(r_up, list) else []) if prev_w <= int(t.get("timestamp", 0)) <= prev_w + 300]
trades_dn = [t for t in (r_dn if isinstance(r_dn, list) else []) if prev_w <= int(t.get("timestamp", 0)) <= prev_w + 300]

print(f"Total UP Trades in Window: {len(trades_up)}")
print(f"Total DOWN Trades in Window: {len(trades_dn)}")

# Match chronological trade pairs
trades_all = []
for t in trades_up:
    trades_all.append({"side_token": "UP", "ts": int(t.get("timestamp", 0)), "price": float(t.get("price", 0)), "size": float(t.get("size", 0)), "side": t.get("side")})
for t in trades_dn:
    trades_all.append({"side_token": "DOWN", "ts": int(t.get("timestamp", 0)), "price": float(t.get("price", 0)), "size": float(t.get("size", 0)), "side": t.get("side")})

trades_all.sort(key=lambda x: x["ts"])

print("\n--- CHRONOLOGICAL TRADE STREAM IN PREVIOUS 5M CANDLE ---")
print("Time (UTC) | Token | Execution Price | Shares Traded | Trade Value (USDC) | Maker Side")
print("-" * 80)
for t in trades_all[-35:]:
    t_str = datetime.datetime.fromtimestamp(t["ts"], tz=datetime.timezone.utc).strftime("%H:%M:%S")
    val = t["price"] * t["size"]
    print(f"{t_str}   | {t['side_token']:4s}  | ${t['price']:.2f}           | {t['size']:8.1f} sh   | ${val:7.2f} USDC     | {t['side']}")

# Let's check the current active market orderbook as well
cur_slug = f"btc-updown-5m-{cur_w}"
r_cur = requests.get(f"{GAMMA_HOST}/events?slug={cur_slug}", timeout=5).json()
if r_cur and r_cur[0].get("markets"):
    m_cur = r_cur[0]["markets"][0]
    tok_cur = json.loads(m_cur.get("clobTokenIds", "[]"))
    b_up = requests.get(f"https://clob.polymarket.com/book?token_id={tok_cur[0]}", timeout=3).json()
    b_dn = requests.get(f"https://clob.polymarket.com/book?token_id={tok_cur[1]}", timeout=3).json()
    
    print(f"\n=======================================================")
    print(f"CURRENT ACTIVE MARKET ORDERBOOK ({cur_slug}):")
    print(f"=======================================================")
    print("UP ASKS (Lowest 5):")
    for a in sorted(b_up.get("asks", []), key=lambda x: float(x["price"]))[:5]:
        print(f"  ${float(a['price']):.2f} -> {float(a['size']):.1f} shares available")
    print("DOWN ASKS (Lowest 5):")
    for a in sorted(b_dn.get("asks", []), key=lambda x: float(x["price"]))[:5]:
        print(f"  ${float(a['price']):.2f} -> {float(a['size']):.1f} shares available")
