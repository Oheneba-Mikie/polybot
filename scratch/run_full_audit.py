import time, datetime, requests, json

headers = {"User-Agent": "Mozilla/5.0"}
GAMMA_HOST = "https://gamma-api.polymarket.com"

# 1. Get current active market
now = int(time.time())
cur_w = (now // 300) * 300
candidates = [cur_w, cur_w + 300, cur_w - 300]
mkt = None

for w_s in candidates:
    slug = f"btc-updown-5m-{w_s}"
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4, headers=headers).json()
        if r and r[0].get("markets"):
            m = r[0]["markets"][0]
            tokens = json.loads(m.get("clobTokenIds", "[]"))
            if len(tokens) >= 2 and now < (w_s + 300):
                mkt = {
                    "slug": slug,
                    "title": r[0].get("title", slug),
                    "window_start": w_s,
                    "window_end": w_s + 300,
                    "up_token": tokens[0],
                    "down_token": tokens[1],
                }
                break
    except Exception:
        pass

if not mkt:
    # fallback to latest available
    slug = f"btc-updown-5m-{cur_w}"
    r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=4, headers=headers).json()
    if r and r[0].get("markets"):
        m = r[0]["markets"][0]
        tokens = json.loads(m.get("clobTokenIds", "[]"))
        mkt = {
            "slug": slug,
            "title": r[0].get("title", slug),
            "window_start": cur_w,
            "window_end": cur_w + 300,
            "up_token": tokens[0],
            "down_token": tokens[1],
        }

print("=== MARKET METADATA ===")
print("Slug:", mkt["slug"])
print("Title:", mkt["title"])
t_rem = max(0, mkt["window_end"] - int(time.time()))
print("Time Remaining:", f"T-{t_rem}s")
end_dt = datetime.datetime.fromtimestamp(mkt["window_end"], tz=datetime.timezone.utc)
print("Resolves At:", end_dt.strftime("%H:%M:%S UTC"))

# 2. Fetch live books
r_up = requests.get(f"https://clob.polymarket.com/book?token_id={mkt['up_token']}", headers=headers).json()
r_dn = requests.get(f"https://clob.polymarket.com/book?token_id={mkt['down_token']}", headers=headers).json()

asks_up = sorted(r_up.get("asks", []), key=lambda x: float(x["price"]))
asks_dn = sorted(r_dn.get("asks", []), key=lambda x: float(x["price"]))

print("\n=== UP ORDER BOOK ASKS ===")
for i, a in enumerate(asks_up[:8], 1):
    print(f"Level {i}: ${float(a['price']):.2f} | Size: {float(a['size']):.1f} shares")

print("\n=== DOWN ORDER BOOK ASKS ===")
for i, a in enumerate(asks_dn[:8], 1):
    print(f"Level {i}: ${float(a['price']):.2f} | Size: {float(a['size']):.1f} shares")

if asks_up and asks_dn:
    best_up_p = float(asks_up[0]["price"])
    best_up_s = float(asks_up[0]["size"])
    best_dn_p = float(asks_dn[0]["price"])
    best_dn_s = float(asks_dn[0]["size"])
    comb = round(best_up_p + best_dn_p, 3)
    print(f"\nBest Ask Spread: UP ${best_up_p:.2f} ({best_up_s:.1f} sh) + DN ${best_dn_p:.2f} ({best_dn_s:.1f} sh) = ${comb:.3f}")

# 3. Fetch live crosses recorded on the Fly.io bot
try:
    r_cloud = requests.get("https://polybot-sniper-mikie.fly.dev/api/state", timeout=4).json()
    crosses = r_cloud.get("cross_opportunities", [])
    print(f"\n=== CLOUD RECORDED LIVE CROSSES ({len(crosses)}) ===")
    for c in crosses[:15]:
        print(f"#{c.get('num')} | {c.get('timestamp')} | UP: {c.get('up_str')} | DN: {c.get('dn_str')} | Comb: {c.get('comb')} | Lifespan: {c.get('lifespan')} | Profit: {c.get('profit')}")
except Exception as e:
    print("Cloud query error:", e)
