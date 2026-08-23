import json
import sys
import datetime

sys.stdout.reconfigure(encoding='utf-8')

with open("scratch/raw_activity_dump.json", "r") as f:
    acts = json.load(f)

redeems = [a for a in acts if a.get("type") == "REDEEM"]

print("="*95)
print(f"THE EXACT {len(redeems)} TRADES THAT HELD TO RESOLUTION (REDEEMED) TODAY:")
print("="*95)
print(f"{'#':<3} | {'REDEEM TIME (UTC)':<19} | {'PAYOUT RECEIVED':<17} | {'SHARES':<7} | {'MARKET NAME'}")
print("-" * 95)

for i, r in enumerate(redeems):
    ts = r.get("timestamp", 0)
    dt_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    sz = float(r.get("size") or 0)
    usdc = float(r.get("usdcSize") or sz)
    title = r.get("title", "")
    print(f"{i+1:<3} | {dt_str:<19} | ${usdc:<16.2f} | {sz:<7.2f} | {title}")

print("="*95)
