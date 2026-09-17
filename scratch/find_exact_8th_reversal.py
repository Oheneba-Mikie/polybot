import requests
import json
import datetime
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"

# The 13 spot reversals from Binance:
reversal_times = [
    (1789678800, "21:00 UTC", "UP", 60.00),
    (1789666200, "17:30 UTC", "DOWN", 78.95),
    (1789661700, "16:15 UTC", "UP", 64.91),
    (1789661100, "16:05 UTC", "DOWN", 72.36),
    (1789660500, "15:55 UTC", "DOWN", 79.91),
    (1789655100, "14:25 UTC", "UP", 133.20),
    (1789650600, "13:10 UTC", "UP", 61.52),
    (1789649400, "12:50 UTC", "UP", 104.31),
    (1789646700, "12:05 UTC", "DOWN", 74.84),
    (1789621200, "05:00 UTC", "UP", 92.32),
    (1789608900, "01:35 UTC", "UP", 136.42),
    (1789603800, "00:10 UTC", "UP", 108.36),
    (1789596300, "22:05 UTC", "DOWN", 71.01)
]

print("=" * 95)
print("AUDITING EVERY REVERSAL CANDLE ON POLYMARKET CLOB TAPE:")
print("=" * 95)

for w_s, t_str, wave_dir, move in reversal_times:
    slug = f"btc-updown-5m-{w_s}"
    r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
    if not r or not r[0].get("markets"):
        continue
    m = r[0]["markets"][0]
    cid = m.get("conditionId")
    outcomes = json.loads(m.get("outcomes") or "[]")
    out_prices = json.loads(m.get("outcomePrices") or "[]")
    if not cid or len(out_prices) < 2:
        continue
    p0, p1 = float(out_prices[0]), float(out_prices[1])
    winner = outcomes[0].upper() if p0 > p1 else outcomes[1].upper()
    loser = outcomes[1].upper() if winner == outcomes[0].upper() else outcomes[0].upper()

    trades = requests.get(f"{DATA_HOST}/trades?market={cid}&limit=1000", timeout=3).json()
    if not isinstance(trades, list):
        continue

    # Find when the losing wave token traded at >= 0.95 or >= 0.98
    losing_trades_at_98 = []
    winning_trades_at_01 = []
    for t in trades:
        px = float(t.get("price", 0))
        oc = str(t.get("outcome", "")).upper()
        tr_ts = t.get("timestamp") or t.get("matchTime")
        if isinstance(tr_ts, str):
            try:
                tr_ts = datetime.datetime.fromisoformat(tr_ts.replace("Z", "+00:00")).timestamp() if "T" in tr_ts else float(tr_ts)
            except:
                tr_ts = 0
        if tr_ts and tr_ts > 1e11:
            tr_ts /= 1000.0
        sec = int(tr_ts - w_s) if tr_ts else 0

        if oc == wave_dir and px >= 0.95:
            losing_trades_at_98.append((sec, px, float(t.get("size", 0))))
        if oc == winner and px <= 0.05:
            winning_trades_at_01.append((sec, px, float(t.get("size", 0))))

    if losing_trades_at_98:
        first_98_sec = losing_trades_at_98[0][0]
        total_98_vol = sum(x[2] for x in losing_trades_at_98)
        print(f"⚠️ Reversal at {t_str} ({slug}):")
        print(f"   Wave: {wave_dir} (${move:.1f}) | Final Winner: {winner}")
        print(f"   Wave token hit >= 0.95 at: T+{first_98_sec}s (Minute {first_98_sec//60 + 1})")
        print(f"   Volume traded at >= 0.95: {total_98_vol:,.0f} shares")
        # When did the true winner surge back?
        winner_surges = [t for t in trades if str(t.get("outcome", "")).upper() == winner and float(t.get("price", 0)) >= 0.50]
        if winner_surges:
            w_ts_s = winner_surges[0].get("timestamp")
            # print first surge sec
            print(f"   Reversal completed: Winner crossed $0.50 late in candle\n")
    else:
        print(f"ℹ️ {t_str}: Spot moved ${move:.1f} briefly, but Polymarket never priced the loser >= 0.95 (market ignored the blip).")
