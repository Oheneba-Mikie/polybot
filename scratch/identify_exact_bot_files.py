import os
import json
import re

# Let's inspect the parameters of all python bot files in the project workspace
workspace_dir = r"c:\Users\mwx1432398\Desktop\antigravity\POLYBOT\polybot"
py_files = [f for f in os.listdir(workspace_dir) if f.endswith('.py')]

bot_specs = {}

for f in py_files:
    path = os.path.join(workspace_dir, f)
    with open(path, 'r', encoding='utf-8', errors='ignore') as file:
        content = file.read()
        
    # Extract key parameters
    conf_match = re.search(r'CONFIDENCE_THRESHOLD\s*=\s*([0-9\.]+)', content)
    win_start_match = re.search(r'BET_WINDOW_START\s*=\s*([0-9]+)', content)
    win_end_match = re.search(r'BET_WINDOW_END\s*=\s*([0-9]+)', content)
    max_price_match = re.search(r'MAX_PRICE_LIMIT\s*=\s*([0-9\.]+)', content)
    
    bot_specs[f] = {
        "confidence_threshold": float(conf_match.group(1)) if conf_match else None,
        "bet_window_start": int(win_start_match.group(1)) if win_start_match else None,
        "bet_window_end": int(win_end_match.group(1)) if win_end_match else None,
        "max_price_limit": float(max_price_match.group(1)) if max_price_match else None,
    }

print("Workspace Python Bot Configurations:")
for b, s in bot_specs.items():
    if any(s.values()):
        print(f"  - {b:<40}: Conf={s['confidence_threshold']} | Start={s['bet_window_start']}s | End={s['bet_window_end']}s | MaxPrice={s['max_price_limit']}")

# Map trade categories directly to Python files
mapping = {
    "five_mins_hybrid_sprint.py / hybrid_sprint_bot.py / off_peak_5mins_hybrid_sprint.py": {
        "description": "5-Min Hybrid Sprint Bots (Conf=0.65, Bet Window T-80s to T-5s)",
        "price_band": "$0.40 - $0.88 (Mid to High)",
        "timing": "T-80s to T-35s entries",
    },
    "close_to_market_bot.py / pure_close_single_stake_bot.py / pure_close_rollover_bot.py": {
        "description": "Close-To-Market / Pure-Close Bots (Bet Window T-12s to T-2s)",
        "price_band": "$0.65 - $0.89",
        "timing": "T-12s to T-2s entries",
    },
    "trend_catcher_rollover_bot.py / scalper_bailout_deploy / trend_catcher_deploy": {
        "description": "Trend Catcher & Scalper Bailout Deployments (High Ask Scalping)",
        "price_band": "$0.90 - $0.99",
        "timing": "Continuous / Late scalp",
    }
}

with open('scratch/exact_bot_mapping.json', 'w') as f:
    json.dump(bot_specs, f, indent=2)

print("\nSaved bot specs.")
