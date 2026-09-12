import requests
import json
import time
import datetime
import sys
from collections import deque
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

TARGET_TOTAL_COST = 0.960
REQUIRED_SHARES   = 5.0
LATENCY_TIERS_MS  = [25, 50, 75, 100, 150, 200, 300, 500, 1000]

now_ts = int(time.time())
w_s = (now_ts // 300) * 300
slug = f"btc-updown-5m-{w_s}"

print("="*115)
print(f"🔬 CONTINUOUS MULTI-OPPORTUNITY EMPIRICAL SCANNER & SURVIVAL MATRIX ({slug})")
print("="*115)

r = requests.get(f"{GAMMA_HOST}/events?slug={slug}").json()
if not r or not r[0].get("markets"):
    print("Market not found!")
    sys.exit(1)

mkt = r[0]["markets"][0]
clob_ids = json.loads(mkt.get("clobTokenIds"))
up_tid = clob_ids[0]
down_tid = clob_ids[1]

# High-resolution buffer of timestamped books
book_buffer = deque(maxlen=2000)

# Accumulators
opportunities = []
survival_matrix = {tier: {"tested": 0, "full": 0, "partial": 0, "missed": 0} for tier in LATENCY_TIERS_MS}
depth_dist = {"ge_5": 0, "ge_10": 0, "ge_20": 0, "ge_50": 0, "ge_100": 0}
up_count = 0
down_count = 0

print("Sampling live order books continuously across 60 seconds (sampling rate: ~30ms)...\n")
start_time = time.time()
sample_count = 0

# Stream order books for 45 seconds to record continuous stream
while time.time() - start_time < 45.0:
    t_now_ms = int(time.time() * 1000)
    try:
        r_up = requests.get(f"{CLOB_HOST}/book?token_id={up_tid}", timeout=1.0).json()
        asks_up = sorted([{"price": float(x["price"]), "size": float(x["size"])} for x in r_up.get("asks", [])], key=lambda x: x["price"])
        book_buffer.append({"ts_ms": t_now_ms, "token_id": up_tid, "asks": asks_up})

        r_down = requests.get(f"{CLOB_HOST}/book?token_id={down_tid}", timeout=1.0).json()
        asks_down = sorted([{"price": float(x["price"]), "size": float(x["size"])} for x in r_down.get("asks", [])], key=lambda x: x["price"])
        book_buffer.append({"ts_ms": t_now_ms, "token_id": down_tid, "asks": asks_down})

        # Scan for opportunities
        for side_name, token_id, asks in [("UP", up_tid, asks_up), ("DOWN", down_tid, asks_down)]:
            if asks:
                best_ask = asks[0]["price"]
                if best_ask <= 0.600:
                    cum_depth = sum([x["size"] for x in asks if x["price"] <= best_ask + 0.03])
                    if cum_depth >= 1.0:
                        opp_id = f"OPP-{len(opportunities)+1:04d}"
                        opportunities.append({
                            "id": opp_id,
                            "side": side_name,
                            "token_id": token_id,
                            "t0_ms": t_now_ms,
                            "t0_best_ask": best_ask,
                            "t0_depth": cum_depth,
                            "asks": asks
                        })
                        if side_name == "UP": up_count += 1
                        else: down_count += 1

                        if cum_depth >= 5.0: depth_dist["ge_5"] += 1
                        if cum_depth >= 10.0: depth_dist["ge_10"] += 1
                        if cum_depth >= 20.0: depth_dist["ge_20"] += 1
                        if cum_depth >= 50.0: depth_dist["ge_50"] += 1
                        if cum_depth >= 100.0: depth_dist["ge_100"] += 1

    except Exception:
        pass
    time.sleep(0.035)

print(f"Recorded {len(book_buffer)} high-resolution book snapshots. Total Opportunities Discovered: {len(opportunities)}\n")

# Replay all opportunities against the continuous ring buffer for each latency tier
for opp in opportunities:
    t0 = opp["t0_ms"]
    tid = opp["token_id"]
    limit_p = opp["t0_best_ask"]

    for tier in LATENCY_TIERS_MS:
        target_t = t0 + tier
        # Find snapshot at target_t
        snap = None
        for s in book_buffer:
            if s["token_id"] == tid and s["ts_ms"] >= target_t:
                snap = s
                break
        
        survival_matrix[tier]["tested"] += 1
        if not snap or not snap.get("asks"):
            survival_matrix[tier]["missed"] += 1
            continue

        matched = 0.0
        for ask in snap["asks"]:
            if ask["price"] <= limit_p:
                matched += ask["size"]
                if matched >= REQUIRED_SHARES: break

        if matched >= REQUIRED_SHARES:
            survival_matrix[tier]["full"] += 1
        elif matched > 0.0:
            survival_matrix[tier]["partial"] += 1
        else:
            survival_matrix[tier]["missed"] += 1

print("="*115)
print("📊 EMPIRICAL LATENCY SURVIVAL DISTRIBUTION TABLE (Reconstructed Timeline)")
print("="*115)
print(f"{'Simulated Latency':<20} | {'Tested Opps':<15} | {'Fully Executable':<20} | {'Partially Exec':<18} | {'Missed / Slipped':<18} | {'Survival %'}")
print("-" * 115)
for tier in LATENCY_TIERS_MS:
    m = survival_matrix[tier]
    t = max(1, m["tested"])
    pct = (m["full"] / t) * 100
    full_str = f"{m['full']} ({pct:.1f}%)"
    part_str = f"{m['partial']} ({m['partial']/t*100:.1f}%)"
    miss_str = f"{m['missed']} ({m['missed']/t*100:.1f}%)"
    print(f"{f'{tier} ms':<20} | {m['tested']:<15} | {full_str:<20} | {part_str:<18} | {miss_str:<18} | {pct:.1f}%")
print("="*115)

print(f"\n📈 OPPORTUNITY FREQUENCY & DEPTH BREAKDOWN:")
print(f"  • Total Candidates Detected in 45s: {len(opportunities)} ({len(opportunities)/(45/60):.1f} opps/min)")
print(f"  • UP Candidates:                   {up_count} ({up_count/max(1,len(opportunities))*100:.1f}%)")
print(f"  • DOWN Candidates:                 {down_count} ({down_count/max(1,len(opportunities))*100:.1f}%)")
print(f"  • Opportunities with >= 5.0 shares:  {depth_dist['ge_5']} ({depth_dist['ge_5']/max(1,len(opportunities))*100:.1f}%)")
print(f"  • Opportunities with >= 10.0 shares: {depth_dist['ge_10']} ({depth_dist['ge_10']/max(1,len(opportunities))*100:.1f}%)")
print(f"  • Opportunities with >= 20.0 shares: {depth_dist['ge_20']} ({depth_dist['ge_20']/max(1,len(opportunities))*100:.1f}%)")
print(f"  • Opportunities with >= 50.0 shares: {depth_dist['ge_50']} ({depth_dist['ge_50']/max(1,len(opportunities))*100:.1f}%)")
print(f"  • Opportunities with >= 100.0 shares:{depth_dist['ge_100']} ({depth_dist['ge_100']/max(1,len(opportunities))*100:.1f}%)")
print("="*115)
