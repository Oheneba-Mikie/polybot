import requests, json, time, datetime, sys

sys.stdout.reconfigure(encoding='utf-8')

out_file = open('scratch/audit_results.txt', 'w', encoding='utf-8')
def p(text):
    print(text)
    out_file.write(text + '\n')
    out_file.flush()

p('='*80)
p('AUDITING RECENT BTC 5M WINDOWS (PRICE DISPLACEMENT & SETTLEMENT ACCURACY)')
p('='*80)

now = int(time.time())
windows_analyzed = []

# Query past 20 5-minute windows
for i in range(1, 21):
    w_s = ((now // 300) - i) * 300
    slug = f'btc-updown-5m-{w_s}'
    try:
        res = requests.get(f'https://gamma-api.polymarket.com/events?slug={slug}', timeout=5).json()
        if res and 'markets' in res[0]:
            mkt = res[0]['markets'][0]
            question = mkt.get('question', '')
            outcomes = json.loads(mkt.get('outcomes', '[]'))
            prices = json.loads(mkt.get('outcomePrices', '[]'))
            
            # Winning side (price == 1)
            winner = None
            for out, p in zip(outcomes, prices):
                if float(p) >= 0.95:
                    winner = out.upper()
            
            # Fetch 5m Kline from Binance for this window to see Open, High, Low, Close, Max Delta
            start_ms = w_s * 1000
            end_ms = (w_s + 300) * 1000
            kline_res = requests.get(f'https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={start_ms}&endTime={end_ms}&limit=5', timeout=5).json()
            
            if kline_res and len(kline_res) > 0:
                open_p = float(kline_res[0][1])
                high_p = max([float(k[2]) for k in kline_res])
                low_p = min([float(k[3]) for k in kline_res])
                close_p = float(kline_res[-1][4])
                
                max_up_delta = high_p - open_p
                max_down_delta = open_p - low_p
                net_delta = close_p - open_p
                
                reached_25_up = max_up_delta >= 25.0
                reached_25_down = max_down_delta >= 25.0
                reached_30_up = max_up_delta >= 30.0
                reached_30_down = max_down_delta >= 30.0
                
                actual_dir = 'UP' if net_delta > 0 else 'DOWN'
                
                time_str = datetime.datetime.fromtimestamp(w_s).strftime('%H:%M')
                windows_analyzed.append({
                    'time': time_str,
                    'open': open_p,
                    'high': high_p,
                    'low': low_p,
                    'close': close_p,
                    'net_delta': net_delta,
                    'max_up': max_up_delta,
                    'max_down': max_down_delta,
                    'winner': winner or actual_dir,
                    'reached_25_up': reached_25_up,
                    'reached_25_down': reached_25_down,
                    'reached_30_up': reached_30_up,
                    'reached_30_down': reached_30_down
                })
    except Exception as e:
        pass

p(f'Total Windows Successfully Audited: {len(windows_analyzed)}')
p('-'*80)
p(f'{"Time":<8} | {"Open":<10} | {"Close":<10} | {"Net Delta":<10} | {"Max Up":<8} | {"Max Dn":<8} | {"Winner":<6} | {"Hit $25?":<9} | {"Hit $30?":<9}')
p('-'*80)

total_30_triggers = 0
correct_30_wins = 0

total_25_triggers = 0
correct_25_wins = 0

for w in reversed(windows_analyzed):
    hit_25 = 'UP ($25)' if w['reached_25_up'] else ('DN ($25)' if w['reached_25_down'] else 'No')
    hit_30 = 'UP ($30)' if w['reached_30_up'] else ('DN ($30)' if w['reached_30_down'] else 'No')
    
    # Check accuracy of $30 trigger
    if w['reached_30_up'] and not w['reached_30_down']:
        total_30_triggers += 1
        if w['winner'] == 'UP': correct_30_wins += 1
    elif w['reached_30_down'] and not w['reached_30_up']:
        total_30_triggers += 1
        if w['winner'] == 'DOWN': correct_30_wins += 1

    # Check accuracy of $25 trigger
    if w['reached_25_up'] and not w['reached_25_down']:
        total_25_triggers += 1
        if w['winner'] == 'UP': correct_25_wins += 1
    elif w['reached_25_down'] and not w['reached_25_up']:
        total_25_triggers += 1
        if w['winner'] == 'DOWN': correct_25_wins += 1

    p(f"{w['time']:^8} | ${w['open']:,.2f} | ${w['close']:,.2f} | {w['net_delta']:>+8.2f} | +${w['max_up']:5.1f} | -${w['max_down']:5.1f} | {w['winner']:^6} | {hit_25:^9} | {hit_30:^9}")

p('='*80)
p('🎯 EMPIRICAL FINDINGS:')
if total_25_triggers > 0:
    p(f"• $25.00 Threshold: Triggered in {total_25_triggers}/{len(windows_analyzed)} windows | Directional Win Rate: {correct_25_wins}/{total_25_triggers} ({correct_25_wins/total_25_triggers*100:.1f}%)")
if total_30_triggers > 0:
    p(f"• $30.00 Threshold: Triggered in {total_30_triggers}/{len(windows_analyzed)} windows | Directional Win Rate: {correct_30_wins}/{total_30_triggers} ({correct_30_wins/total_30_triggers*100:.1f}%)")
p('='*80)
