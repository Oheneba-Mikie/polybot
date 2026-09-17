import requests
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    r = requests.get('http://127.0.0.1:8080/api/state', timeout=5)
    print('HTTP Status:', r.status_code)
    d = r.json()
    print("Market:", d.get("current_candle_slug"))
    print("UP Ask:", f"${d.get('live_up_ask'):.2f}", f"({d.get('live_up_depth'):.1f} sh)")
    print("DOWN Ask:", f"${d.get('live_down_ask'):.2f}", f"({d.get('live_down_depth'):.1f} sh)")
    print("Combined Cost:", f"${d.get('combined_cost'):.3f}")
    print("Quota Used:", f"{d.get('trades_in_window')}/{d.get('max_trades_per_window')}")
    print("Depth Met (>=100sh):", d.get("depth_condition_met"))
    print("Profit Condition Met (<=0.98):", d.get("price_condition_met"))
    print("Status:", d.get("status"))
except Exception as e:
    print("Error:", e)
