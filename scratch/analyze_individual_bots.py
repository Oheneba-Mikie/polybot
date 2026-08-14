import json
import os
import re

with open('scratch/analyzed_trades.json', encoding='utf-8') as f:
    trades = json.load(f)

workspace_dir = r"c:\Users\mwx1432398\Desktop\antigravity\POLYBOT\polybot"
py_files = [f for f in os.listdir(workspace_dir) if f.endswith('.py') and not f.startswith('test') and not f.startswith('generate') and not f.startswith('query') and not f.startswith('track') and not f.startswith('probe') and not f.startswith('webconsole') and not f.startswith('thispy')]

bot_definitions = {}

for f in py_files:
    path = os.path.join(workspace_dir, f)
    with open(path, 'r', encoding='utf-8', errors='ignore') as file:
        content = file.read()

    conf_m = re.search(r'CONFIDENCE_THRESHOLD\s*=\s*([0-9\.]+)', content)
    win_s = re.search(r'BET_WINDOW_START\s*=\s*([0-9]+)', content)
    win_e = re.search(r'BET_WINDOW_END\s*=\s*([0-9]+)', content)
    max_p = re.search(r'MAX_PRICE_LIMIT\s*=\s*([0-9\.]+)', content)

    conf = float(conf_m.group(1)) if conf_m else 0.65
    w_start = int(win_s.group(1)) if win_s else 80
    w_end = int(win_e.group(1)) if win_e else 5
    max_price = float(max_p.group(1)) if max_p else 1.00

    bot_definitions[f] = {
        "conf": conf,
        "w_start": w_start,
        "w_end": w_end,
        "max_price": max_price,
    }

individual_results = {}

for bot_name, spec in bot_definitions.items():
    matching_trades = []
    wins = 0
    losses = 0
    unresolved = 0
    pnl = 0.0
    volume = 0.0

    for t in trades:
        price = t.get('price', 0)
        size = t.get('usdc_size', 0)
        is_win = t.get('is_win')
        ts = t.get('timestamp', 0)
        rem_sec = 300 - (ts % 300)

        in_window = (spec['w_end'] - 2 <= rem_sec <= spec['w_start'] + 5)
        price_ok = (price <= spec['max_price'])

        if in_window and price_ok:
            matching_trades.append(t)
            volume += size
            if is_win is True:
                wins += 1
                payout = size / price if price > 0 else size
                pnl += (payout - size)
            elif is_win is False:
                losses += 1
                pnl -= size
            else:
                unresolved += 1

    total_settled = wins + losses
    win_rate = (wins / total_settled * 100) if total_settled > 0 else 0.0

    individual_results[bot_name] = {
        "total_trades": len(matching_trades),
        "wins": wins,
        "losses": losses,
        "unresolved": unresolved,
        "win_rate_pct": round(win_rate, 1),
        "volume_usd": round(volume, 2),
        "pnl_usd": round(pnl, 2),
        "spec": spec
    }

print("\n" + "="*95)
print("  INDIVIDUAL BOT SCRIPT PERFORMANCE REPORT")
print("="*95)

for bot_name, r in sorted(individual_results.items(), key=lambda x: (x[1]['total_trades'] > 0, x[1]['win_rate_pct']), reverse=True):
    if r['total_trades'] == 0:
        continue
    spec = r['spec']
    print(f"\n[FILE] {bot_name}")
    print(f"   - Rules Configured  : Conf={spec['conf']} | Window=T-{spec['w_start']}s to T-{spec['w_end']}s | MaxPrice=${spec['max_price']:.2f}")
    print(f"   - Total Trades      : {r['total_trades']} (Settled: {r['wins'] + r['losses']})")
    print(f"   - Wins / Losses     : {r['wins']} W / {r['losses']} L")
    print(f"   - WIN RATE          : {r['win_rate_pct']}%")
    print(f"   - Total Volume      : ${r['volume_usd']:.2f}")
    print(f"   - Net P&L           : ${r['pnl_usd']:+.2f}")

with open('scratch/individual_bot_report.json', 'w', encoding='utf-8') as f:
    json.dump(individual_results, f, indent=2)
