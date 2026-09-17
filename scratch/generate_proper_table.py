import os, sys, time, json, datetime, requests
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"
headers = {"User-Agent": "Mozilla/5.0"}

def audit_candle_detailed(asset_prefix, w_s):
    slug = f"{asset_prefix}-updown-5m-{w_s}"
    w_e = w_s + 300
    t_start_utc = datetime.datetime.fromtimestamp(w_s, tz=datetime.timezone.utc).strftime("%H:%M")
    t_end_utc   = datetime.datetime.fromtimestamp(w_e, tz=datetime.timezone.utc).strftime("%H:%M UTC")
    
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", headers=headers, timeout=5).json()
        if not r or not r[0].get("markets"):
            return {
                "asset": asset_prefix.upper(),
                "time_window": f"{t_start_utc} - {t_end_utc}",
                "slug": slug,
                "status": "Market Not Opened",
                "up_shares": "0 sh",
                "dn_shares": "0 sh",
                "comb_cost": "N/A",
                "profit": "N/A",
                "depth_status": "❌ No Depth"
            }
        
        m = r[0]["markets"][0]
        clob_tokens = json.loads(m.get("clobTokenIds", "[]")) if isinstance(m.get("clobTokenIds"), str) else m.get("clobTokenIds", [])
        outcome_prices = json.loads(m.get("outcomePrices", "[]")) if isinstance(m.get("outcomePrices"), str) else m.get("outcomePrices", [])
        
        if len(clob_tokens) < 2:
            return {
                "asset": asset_prefix.upper(),
                "time_window": f"{t_start_utc} - {t_end_utc}",
                "slug": slug,
                "status": "No Tokens",
                "up_shares": "0 sh",
                "dn_shares": "0 sh",
                "comb_cost": "N/A",
                "profit": "N/A",
                "depth_status": "❌ No Depth"
            }
        
        up_token, dn_token = clob_tokens[0], clob_tokens[1]
        
        r_up = requests.get(f"{DATA_HOST}/trades?asset_id={up_token}&limit=200", headers=headers, timeout=5).json()
        r_dn = requests.get(f"{DATA_HOST}/trades?asset_id={dn_token}&limit=200", headers=headers, timeout=5).json()
        
        up_trades = r_up if isinstance(r_up, list) else []
        dn_trades = r_dn if isinstance(r_dn, list) else []
        
        up_w = [t for t in up_trades if w_s <= int(t.get("timestamp", 0)) <= w_e]
        dn_w = [t for t in dn_trades if w_s <= int(t.get("timestamp", 0)) <= w_e]
        
        if not up_w and not dn_w:
            # Check if there is order book historical info or if it resolved without trades
            res_str = "Resolved" if outcome_prices else "0 Trades"
            return {
                "asset": asset_prefix.upper(),
                "time_window": f"{t_start_utc} - {t_end_utc}",
                "slug": slug,
                "status": f"{res_str} (0 Trades)",
                "up_shares": "0 sh",
                "dn_shares": "0 sh",
                "comb_cost": "$1.000",
                "profit": "0.0%",
                "depth_status": "❌ Dried/Empty"
            }
            
        min_up_p = min([float(t["price"]) for t in up_w]) if up_w else 0.50
        min_dn_p = min([float(t["price"]) for t in dn_w]) if dn_w else 0.50
        
        max_up_size = max([float(t.get("size", 0)) for t in up_w]) if up_w else 0.0
        max_dn_size = max([float(t.get("size", 0)) for t in dn_w]) if dn_w else 0.0
        
        comb = round(min_up_p + min_dn_p, 3)
        profit_per_sh = round(1.00 - comb, 3)
        profit_pct = round((profit_per_sh / comb) * 100, 1) if comb > 0 else 0.0
        
        depth_tag = "❌ <50 sh"
        if max_up_size >= 100 and max_dn_size >= 100:
            depth_tag = "🚀 100+ sh"
        elif max_up_size >= 50 and max_dn_size >= 50:
            depth_tag = "⚡ 50+ sh"
            
        profit_str = f"+${profit_per_sh:.3f} (+{profit_pct:.1f}%)" if comb < 1.000 else "No Arb ($1.00+)"
        
        return {
            "asset": asset_prefix.upper(),
            "time_window": f"{t_start_utc} - {t_end_utc}",
            "slug": slug,
            "status": f"{len(up_w) + len(dn_w)} Trades",
            "up_shares": f"{max_up_size:.1f} sh @ ${min_up_p:.2f}",
            "dn_shares": f"{max_dn_size:.1f} sh @ ${min_dn_p:.2f}",
            "comb_cost": f"${comb:.3f}",
            "profit": profit_str,
            "depth_status": depth_tag
        }
    except Exception as e:
        return {
            "asset": asset_prefix.upper(),
            "time_window": f"{t_start_utc} - {t_end_utc}",
            "slug": slug,
            "status": "Error",
            "up_shares": "0 sh",
            "dn_shares": "0 sh",
            "comb_cost": "N/A",
            "profit": "N/A",
            "depth_status": "Error"
        }

now = int(time.time())
cur_w = (now // 300) * 300
past_windows = [cur_w - i * 300 for i in range(1, 25)]
past_windows.reverse()

with ThreadPoolExecutor(max_workers=10) as ex:
    eth_data = list(ex.map(lambda w: audit_candle_detailed("eth", w), past_windows))
    sol_data = list(ex.map(lambda w: audit_candle_detailed("sol", w), past_windows))

print("=== ETH DATA ===")
print(json.dumps(eth_data, indent=2))
print("=== SOL DATA ===")
print(json.dumps(sol_data, indent=2))
