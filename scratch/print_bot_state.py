import requests, sys

sys.stdout.reconfigure(encoding='utf-8')

r = requests.get('https://polybot-sniper-mikie.fly.dev/api/state', timeout=10).json()
print(f"Status: {r.get('status')}", flush=True)
print(f"Min Persistence: {r.get('min_persistence_secs')} seconds", flush=True)
print(f"Cross Persisted: {r.get('cross_persisted_s')} seconds", flush=True)
print(f"Trades in Window: {r.get('trades_in_window')}", flush=True)
print(f"Wallet Balance: ${r.get('wallet_balance')}", flush=True)
print("\n--- LATEST LOGS ---", flush=True)
for l in r.get('logs', [])[-10:]:
    print(l, flush=True)
