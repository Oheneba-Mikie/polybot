import os
import sys
import time
import json
import datetime
import requests
import statistics
from collections import deque

sys.stdout.reconfigure(encoding='utf-8')

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"
TARGET_TOTAL_COST = 0.960

print("="*140)
print("🔬 FULL LIVE 5-MINUTE WINDOW AUDIT: CONTINUOUS SEQUENTIAL CAPTURABLE DEPTH EXPERIMENT")
print("="*140)

# 1. Target the exact upcoming full 5-minute candle
now = time.time()
target_start_ts = int(now // 300) * 300
if now - target_start_ts > 30: # If we are more than 30s into current candle, target the next fresh candle
    target_start_ts += 300

target_end_ts = target_start_ts + 300
target_slug = f"btc-updown-5m-{target_start_ts}"

start_str = datetime.datetime.fromtimestamp(target_start_ts, datetime.timezone.utc).strftime("%H:%M:%S")
end_str   = datetime.datetime.fromtimestamp(target_end_ts, datetime.timezone.utc).strftime("%H:%M:%S")

print(f"🎯 Target Full Candle: {target_slug} (From {start_str} to {end_str} UTC)")

# Wait until candle starts if in the future
time_to_start = target_start_ts - time.time()
if time_to_start > 0:
    print(f"⏳ Waiting {time_to_start:.1f}s until window start ({start_str} UTC)...")
    time.sleep(time_to_start)

# Fetch market tokens
print(f"🚀 Window started! Fetching token IDs for {target_slug}...")
tokens = None
for _ in range(10):
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={target_slug}", timeout=3).json()
        if r and r[0].get("markets"):
            m = r[0]["markets"][0]
            clob_ids = json.loads(m.get("clobTokenIds") or "[]")
            outcomes = json.loads(m.get("outcomes") or "[]")
            up_id = clob_ids[0] if outcomes[0].upper() == "UP" else clob_ids[1]
            down_id = clob_ids[1] if outcomes[0].upper() == "UP" else clob_ids[0]
            tokens = {"up_id": up_id, "down_id": down_id}
            break
    except Exception:
        pass
    time.sleep(0.5)

if not tokens:
    print("❌ Failed to fetch tokens for candle!")
    sys.exit(1)

up_id = tokens["up_id"]
down_id = tokens["down_id"]
print(f"✅ Active Tokens: UP={up_id} | DOWN={down_id}")

# Real-time state structures
book_timeline = deque(maxlen=15000) # High-resolution timeline of all snapshots
rtt_samples = []

session = requests.Session()
start_run = time.time()

# We monitor until the candle reaches target_end_ts (full 5 minutes)
print(f"📡 Continuously recording high-frequency order books and measuring CLOB latency until {end_str} UTC...\n")

leg1_entries = [] # List of filled Leg 1 opportunities
last_scanned_prices = {"UP": None, "DOWN": None}
opp_counter = 0

while time.time() < target_end_ts:
    t_now = time.time()
    t_now_ms = int(t_now * 1000)

    # Periodic latency measurement (every ~5 seconds)
    if len(rtt_samples) == 0 or int(t_now) % 5 == 0 and (t_now_ms % 1000 < 50):
        t_s = time.perf_counter()
        try:
            session.get(f"{CLOB_HOST}/time", timeout=1.0)
            rtt_samples.append((time.perf_counter() - t_s) * 1000 + 40.0) # Network RTT + signing + matching
        except Exception:
            pass

    curr_bot_latency = int(statistics.median(rtt_samples)) if rtt_samples else 390

    # Fetch UP & DOWN order books
    try:
        r_up = session.get(f"{CLOB_HOST}/book?token_id={up_id}", timeout=1.0).json()
        asks_up = sorted([{"price": float(x["price"]), "size": float(x["size"])} for x in r_up.get("asks", [])], key=lambda x: x["price"])
        book_timeline.append({"ts_ms": t_now_ms, "token_id": up_id, "side": "UP", "asks": asks_up})

        r_down = session.get(f"{CLOB_HOST}/book?token_id={down_id}", timeout=1.0).json()
        asks_down = sorted([{"price": float(x["price"]), "size": float(x["size"])} for x in r_down.get("asks", [])], key=lambda x: x["price"])
        book_timeline.append({"ts_ms": t_now_ms, "token_id": down_id, "side": "DOWN", "asks": asks_down})

        # Scan for Leg 1 Qualifying Opportunities
        for side_name, token_id, asks in [("UP", up_id, asks_up), ("DOWN", down_id, asks_down)]:
            if asks:
                best_ask = asks[0]["price"]
                best_sz = asks[0]["size"]

                if best_ask <= 0.600:
                    # De-duplicate identical price scans within 200ms
                    last_px = last_scanned_prices[side_name]
                    if last_px == (best_ask, best_sz):
                        continue
                    last_scanned_prices[side_name] = (best_ask, best_sz)

                    opp_counter += 1
                    leg1_entries.append({
                        "opp_id": f"OPP-{opp_counter:04d}",
                        "t0_ms": t_now_ms,
                        "side": side_name,
                        "token_id": token_id,
                        "opp_side": "DOWN" if side_name == "UP" else "UP",
                        "opp_token_id": down_id if side_name == "UP" else up_id,
                        "price_t0": best_ask,
                        "disp_depth_t0": best_sz,
                        "latency_ms": curr_bot_latency,
                        "t1_exec_ms": t_now_ms + curr_bot_latency,
                        "max_leg2_price": round(TARGET_TOTAL_COST - best_ask, 4),
                        # Results populated after execution
                        "leg1_filled": False,
                        "leg1_capturable_depth": 0.0,
                        "leg2_available": False,
                        "leg2_t_reach_ms": None,
                        "inter_leg_delay_ms": None,
                        "leg2_disp_depth": 0.0,
                        "leg2_surviving_depth": 0.0,
                        "leg2_capturable_depth": 0.0,
                        "can_5": False,
                        "can_10": False,
                        "can_20": False,
                        "can_50": False,
                        "can_100": False
                    })
    except Exception:
        pass

    time.sleep(0.025)

print(f"\n🏁 Window ended at {end_str} UTC! Recorded {len(book_timeline)} total book states and {len(leg1_entries)} Leg 1 detection events.")
print("Evaluating post-latency execution and subsequent Leg 2 arrival across the complete timeline...\n")

# ==============================================================================
# POST-PROCESSING TIMELINE REPLAY: LEG 1 EXECUTION & DYNAMIC LEG 2 ARRIVAL
# ==============================================================================
for entry in leg1_entries:
    t0_ms = entry["t0_ms"]
    t1_exec_ms = entry["t1_exec_ms"]
    side1 = entry["side"]
    token1 = entry["token_id"]
    px1 = entry["price_t0"]
    disp1 = entry["disp_depth_t0"]
    max_p2 = entry["max_leg2_price"]
    opp_token = entry["opp_token_id"]
    opp_side = entry["opp_side"]
    lat_ms = entry["latency_ms"]

    # 1. Evaluate Leg 1 Execution at T1_exec (after latency)
    snap_t1 = None
    for s in book_timeline:
        if s["token_id"] == token1 and s["ts_ms"] >= t1_exec_ms:
            snap_t1 = s
            break

    if snap_t1 and snap_t1.get("asks"):
        asks1 = snap_t1["asks"]
        post_px1 = asks1[0]["price"]
        post_sz1 = asks1[0]["size"]
        if post_px1 <= px1:
            surviving1 = post_sz1
            # 50% queue position assumption
            capturable1 = max(0.0, surviving1 - (disp1 * 0.50))
            entry["leg1_capturable_depth"] = round(capturable1, 1)
            if capturable1 >= 1.0: # Minimum 1 share executable
                entry["leg1_filled"] = True
        else:
            entry["leg1_capturable_depth"] = 0.0

    if not entry["leg1_filled"]:
        continue # Leg 1 failed to execute

    # 2. Track Opposing Leg 2 Arrival from T1_exec until candle end
    snap_leg2_reach = None
    for s in book_timeline:
        if s["token_id"] == opp_token and s["ts_ms"] >= t1_exec_ms:
            if s.get("asks") and s["asks"][0]["price"] <= max_p2:
                snap_leg2_reach = s
                break

    if snap_leg2_reach:
        entry["leg2_available"] = True
        t_reach_ms = snap_leg2_reach["ts_ms"]
        entry["leg2_t_reach_ms"] = t_reach_ms
        entry["inter_leg_delay_ms"] = t_reach_ms - t1_exec_ms
        
        disp_depth_2 = snap_leg2_reach["asks"][0]["size"]
        reach_px_2 = snap_leg2_reach["asks"][0]["price"]
        entry["leg2_disp_depth"] = disp_depth_2

        # 3. Simulate Our Bot's Latency on Leg 2 (T_reach + Latency)
        t_leg2_exec_ms = t_reach_ms + lat_ms
        snap_leg2_post = None
        for s in book_timeline:
            if s["token_id"] == opp_token and s["ts_ms"] >= t_leg2_exec_ms:
                snap_leg2_post = s
                break

        if snap_leg2_post and snap_leg2_post.get("asks"):
            asks2_post = snap_leg2_post["asks"]
            p2_post = asks2_post[0]["price"]
            sz2_post = asks2_post[0]["size"]

            if p2_post <= reach_px_2:
                surviving2 = sz2_post
                # 50% queue position assumption on Leg 2
                capturable2 = max(0.0, surviving2 - (disp_depth_2 * 0.50))
                entry["leg2_surviving_depth"] = round(surviving2, 1)
                entry["leg2_capturable_depth"] = round(capturable2, 1)

                entry["can_5"]   = (capturable2 >= 5.0)
                entry["can_10"]  = (capturable2 >= 10.0)
                entry["can_20"]  = (capturable2 >= 20.0)
                entry["can_50"]  = (capturable2 >= 50.0)
                entry["can_100"] = (capturable2 >= 100.0)

# ==============================================================================
# COMPILE RESULTS & PRINT THE 8 CORE REQUIREMENTS
# ==============================================================================
total_leg1_fills = sum([1 for e in leg1_entries if e["leg1_filled"]])
opp_became_avail = sum([1 for e in leg1_entries if e["leg1_filled"] and e["leg2_available"]])
avail_pct = (opp_became_avail / max(1, total_leg1_fills)) * 100

delays = [e["inter_leg_delay_ms"] for e in leg1_entries if e["leg1_filled"] and e["leg2_available"]]
med_delay = statistics.median(delays) if delays else 0.0
mean_delay = statistics.mean(delays) if delays else 0.0

leg2_disp_depths = [e["leg2_disp_depth"] for e in leg1_entries if e["leg1_filled"] and e["leg2_available"]]
med_leg2_disp = statistics.median(leg2_disp_depths) if leg2_disp_depths else 0.0

leg2_capt_depths = [e["leg2_capturable_depth"] for e in leg1_entries if e["leg1_filled"] and e["leg2_available"]]
med_leg2_capt = statistics.median(leg2_capt_depths) if leg2_capt_depths else 0.0

can_5_cnt   = sum([1 for e in leg1_entries if e["leg1_filled"] and e["can_5"]])
can_10_cnt  = sum([1 for e in leg1_entries if e["leg1_filled"] and e["can_10"]])
can_20_cnt  = sum([1 for e in leg1_entries if e["leg1_filled"] and e["can_20"]])
can_50_cnt  = sum([1 for e in leg1_entries if e["leg1_filled"] and e["can_50"]])
can_100_cnt = sum([1 for e in leg1_entries if e["leg1_filled"] and e["can_100"]])

med_lat = statistics.median(rtt_samples) if rtt_samples else 390.0

print("="*140)
print("🏆 CORE EXPERIMENTAL RESULTS (CURRENT 5-MINUTE LIVE MARKET)")
print("="*140)
print(f"1. Number of Leg 1 fills:                                           {total_leg1_fills}")
print(f"2. Number of times opposite leg subsequently became available:      {opp_became_avail}")
print(f"3. Percentage of Leg 1 fills where opposite leg became available:   {avail_pct:.1f}%")
print(f"4. Median delay until opposite leg became available:                {med_delay:,.0f} ms ({med_delay/1000.0:.2f} seconds) [Mean: {mean_delay/1000.0:.2f}s]")
print(f"5. Median FULL displayed depth on Leg 2 when it became available:   {med_leg2_disp:,.1f} shares")
print(f"6. Median REALISTICALLY CAPTURABLE depth after actual bot latency: {med_leg2_capt:,.1f} shares (Measured Bot Latency: {med_lat:.0f}ms)")
print(f"7. Number of times we could realistically capture:")
print(f"   • >= 5 shares:   {can_5_cnt} times ({can_5_cnt/max(1,total_leg1_fills)*100:.1f}%)")
print(f"   • >= 10 shares:  {can_10_cnt} times ({can_10_cnt/max(1,total_leg1_fills)*100:.1f}%)")
print(f"   • >= 20 shares:  {can_20_cnt} times ({can_20_cnt/max(1,total_leg1_fills)*100:.1f}%)")
print(f"   • >= 50 shares:  {can_50_cnt} times ({can_50_cnt/max(1,total_leg1_fills)*100:.1f}%)")
print(f"   • >= 100 shares: {can_100_cnt} times ({can_100_cnt/max(1,total_leg1_fills)*100:.1f}%)")
print("="*140)

print("\n" + "="*140)
print("📜 8. EXACT OCCURRENCE LOG (ALL SEQUENTIAL EVENTS IN CURRENT WINDOW)")
print("="*140)

valid_events = [e for e in leg1_entries if e["leg1_filled"]]
for idx, e in enumerate(valid_events):
    t0_dt = datetime.datetime.fromtimestamp(e["t0_ms"]/1000.0, datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    if e["leg2_available"]:
        t2_dt = datetime.datetime.fromtimestamp(e["leg2_t_reach_ms"]/1000.0, datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-3]
        delay_s = f"{e['inter_leg_delay_ms']/1000.0:.2f}s"
        status_s = f"✅ FILLED (Capturable: {e['leg2_capturable_depth']:.1f} sh | >=5sh: {'YES' if e['can_5'] else 'NO'})"
    else:
        t2_dt = "EXPIRED"
        delay_s = "Never"
        status_s = "❌ Leg 2 Never Reached Ceiling Before Expiry"

    print(f"[{idx+1:03d}] {t0_dt} | Leg 1: BUY {e['side']} @ ${e['price_t0']:.3f} (Capt: {e['leg1_capturable_depth']:.1f}sh) -> Leg 2 Target: <= ${e['max_leg2_price']:.3f} | Leg 2 Reached: {t2_dt} (Delay: {delay_s}) | Disp Depth: {e['leg2_disp_depth']:.1f}sh | Latency: {e['latency_ms']}ms | {status_s}")
print("="*140)
