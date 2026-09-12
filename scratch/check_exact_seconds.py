import requests
import datetime

# Query exact 1-second prices from Binance for 14:10:15 to 14:10:45 UTC on Sep 10, 2026
dt_start = datetime.datetime(2026, 9, 10, 14, 10, 15, tzinfo=datetime.timezone.utc)
dt_end = datetime.datetime(2026, 9, 10, 14, 10, 45, tzinfo=datetime.timezone.utc)
start_ms = int(dt_start.timestamp() * 1000)
end_ms = int(dt_end.timestamp() * 1000)

url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1s&startTime={start_ms}&endTime={end_ms}"
r = requests.get(url)
if r.status_code == 200:
    klines = r.json()
    ptb = 77040.01
    print("=== EXACT SECOND-BY-SECOND BTC MOVES AROUND ENTRY (14:10:15 - 14:10:45 UTC) ===")
    print(f"Price to Beat (PTB): ${ptb:,.2f}")
    print("-" * 75)
    for k in klines:
        t = datetime.datetime.fromtimestamp(k[0]/1000, datetime.timezone.utc).strftime('%H:%M:%S')
        o = float(k[1])
        h = float(k[2])
        l = float(k[3])
        c = float(k[4])
        v = float(k[5])
        diff = c - ptb
        d_str = f"+${diff:.2f}" if diff >= 0 else f"-${abs(diff):.2f}"
        
        note = ""
        if t == "14:10:27":
            note = " <--- BOT BOUGHT DOWN @ $0.4800 (Needs DOWN bid to reach $0.49)"
        elif t in ("14:10:28", "14:10:29", "14:10:30"):
            note = " <--- REVERSAL SPIKE!"
            
        print(f"[{t}] Open: ${o:,.2f} | High: ${h:,.2f} | Low: ${l:,.2f} | Close: ${c:,.2f} | Diff vs PTB: {d_str:<8} {note}")
else:
    print("Error querying Binance 1s klines:", r.status_code)
