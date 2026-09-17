import requests
import json
import time
import datetime
import sys
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

now = int(time.time())
cur_w = (now // 300) * 300
windows = [cur_w - (i * 300) for i in range(1, 90)]

def scan_window(w_s):
    res_list = []
    for coin in ["btc", "eth"]:
        slug = f"{coin}-updown-5m-{w_s}"
        try:
            r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
            if not r or not r[0].get("markets"):
                continue
            m = r[0]["markets"][0]
            cid = m.get("conditionId")
            out_prices = json.loads(m.get("outcomePrices") or "[]")
            outcomes = json.loads(m.get("outcomes") or "[]")
            if not cid or len(out_prices) < 2:
                continue

            trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=2000", timeout=3).json()
            if not isinstance(trades, list) or len(trades) < 10:
                continue

            parsed = []
            for t in trades:
                tr_ts = t.get("timestamp") or t.get("matchTime")
                if isinstance(tr_ts, str):
                    try:
                        tr_ts = datetime.datetime.fromisoformat(tr_ts.replace("Z", "+00:00")).timestamp() if "T" in tr_ts else float(tr_ts)
                    except:
                        tr_ts = 0
                if tr_ts and tr_ts > 1e11:
                    tr_ts /= 1000.0

                if w_s <= tr_ts <= w_s + 300:
                    parsed.append({
                        "ts": tr_ts,
                        "sec": int(tr_ts - w_s),
                        "price": float(t.get("price", 0)),
                        "size": float(t.get("size", 0)),
                        "side": str(t.get("side", "")).upper(),
                        "outcome": str(t.get("outcome", "")).upper()
                    })

            if not parsed:
                continue
            parsed.sort(key=lambda x: x["ts"])

            p0 = float(out_prices[0])
            p1 = float(out_prices[1])
            if p0 == p1:
                continue
            final_winner = outcomes[0].upper() if p0 > p1 else outcomes[1].upper()
            final_loser  = outcomes[1].upper() if final_winner == outcomes[0].upper() else outcomes[0].upper()

            wave_98_trades = [t for t in parsed if t["price"] >= 0.975 and t["side"] == "BUY"]
            if not wave_98_trades:
                continue

            first_98 = wave_98_trades[0]
            token_surged = first_98["outcome"]
            token_crushed = outcomes[1].upper() if token_surged == outcomes[0].upper() else outcomes[0].upper()

            did_reverse = (token_surged != final_winner)

            subsequent_other_trades = [t for t in parsed if t["ts"] >= first_98["ts"] and t["outcome"] == token_crushed]
            subsequent_01_trades = [t for t in subsequent_other_trades if t["price"] <= 0.015]
            min_other_price = min([t["price"] for t in subsequent_other_trades]) if subsequent_other_trades else 1.0

            res_list.append({
                "slug": slug,
                "window_start": w_s,
                "token_surged": token_surged,
                "token_crushed": token_crushed,
                "final_winner": final_winner,
                "final_loser": final_loser,
                "first_98_sec": first_98["sec"],
                "first_98_ts": first_98["ts"],
                "first_98_px": first_98["price"],
                "first_98_sz": first_98["size"],
                "did_reverse": did_reverse,
                "min_other_price": min_other_price,
                "has_01": len(subsequent_01_trades) > 0,
                "trades": parsed
            })
        except Exception:
            pass
    return res_list

print("Scanning historical markets in parallel...")
all_results = []
with ThreadPoolExecutor(max_workers=10) as ex:
    for res in ex.map(scan_window, windows):
        all_results.extend(res)

reversals = [r for r in all_results if r["did_reverse"]]
non_01s = [r for r in all_results if not r["did_reverse"] and not r["has_01"]]

print(f"Total wave markets (>= 0.98 hit): {len(all_results)}")
print(f"Reversals (0.98 hit but LOST): {len(reversals)}")
print(f"Markets where loser NEVER hit $0.01: {len(non_01s)}")

print("\n" + "="*95)
print("🚨 FORENSIC TICK-BY-TICK BREAKDOWN OF REVERSALS")
print("="*95)

for idx, rev in enumerate(reversals):
    t_start = datetime.datetime.fromtimestamp(rev["window_start"], datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\nCASE #{idx+1}: {rev['slug']} ({t_start})")
    print(f"  • Token that surged: {rev['token_surged']} (Hit ${rev['first_98_px']} at T+{rev['first_98_sec']}s)")
    print(f"  • Result: {rev['final_winner']} WON! {rev['token_surged']} CRASHED TO $0.00!")
    print(f"  • Lowest price other token reached before reversal: ${rev['min_other_price']:.3f}")
    
    # Analyze trade sequence after 0.98
    trades = rev["trades"]
    after_98 = [t for t in trades if t["sec"] >= rev["first_98_sec"]]
    
    print("\n  Detailed Trade Flow After $0.98 Spike:")
    # Group trades by second or significant price shifts
    last_p = {}
    for t in after_98:
        out = t["outcome"]
        p = t["price"]
        sec = t["sec"]
        side = t["side"]
        sz = t["size"]
        # Print if new price level or important transition
        if out not in last_p or abs(last_p[out] - p) >= 0.05 or sec in [rev["first_98_sec"], 280, 290, 295, 298, 299, 300]:
            last_p[out] = p
            print(f"    [T+{sec:03d}s] {out:<5} {side:<4} @ ${p:.3f} | Size: {sz:6.1f} sh")

print("\n" + "="*95)
print("🔍 FORENSIC BREAKDOWN: WHY DID THE LOSER NEVER REACH $0.01?")
print("="*95)

for idx, nom in enumerate(non_01s[:4]):
    t_start = datetime.datetime.fromtimestamp(nom["window_start"], datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\nCASE #{idx+1}: {nom['slug']} ({t_start})")
    print(f"  • {nom['token_surged']} hit 0.98 at T+{nom['first_98_sec']}s")
    print(f"  • Winner: {nom['final_winner']} | Loser: {nom['final_loser']}")
    print(f"  • Lowest price traded on Loser ({nom['token_crushed']}): ${nom['min_other_price']:.3f}")
    
    # Trade sequence on loser in final 60 seconds
    loser_trades = [t for t in nom["trades"] if t["outcome"] == nom["token_crushed"] and t["sec"] >= nom["first_98_sec"]]
    print(f"  • Trades on Loser after 0.98 hit:")
    for t in loser_trades[:6]:
        print(f"    [T+{t['sec']:03d}s] {t['outcome']} {t['side']} @ ${t['price']:.3f} ({t['size']:.1f} sh)")
