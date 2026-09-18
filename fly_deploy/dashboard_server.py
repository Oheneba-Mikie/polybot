import http.server
import socketserver
import threading
import json
import time
import datetime
import requests

# Shared state updated by wave_fear_sniper.py
live_state = {
    "status": "HUNTING",
    "status_detail": "Scanning BTC 5M candle...",
    "btc_spot": 0.0,
    "btc_open": 0.0,
    "btc_move": 0.0,
    "t_elapsed": 0,
    "t_rem": 300,
    "market_title": "Loading active market...",
    "up_ask": 1.0,
    "down_ask": 1.0,
    "active_shares": 5.0,
    "streak_count": 6,
    "total_streak_profit": 1.62,
    "usdc_balance": 11.49,
    "last_updated": ""
}

session = requests.Session()

def get_recent_trades_from_api(poly_address="0x81ad69942a32f7b1df4d16f0c3f79311f55de50a"):
    try:
        r = session.get(f"https://data-api.polymarket.com/activity?user={poly_address}&limit=20", timeout=2.5).json()
        by_market = {}
        for a in r:
            title = a.get("title", "")
            if "September" in title or "October" in title or "Up or Down" in title:
                by_market.setdefault(title, []).append(a)
        
        trades_list = []
        for idx, (title, acts) in enumerate(reversed(list(by_market.items()))):
            spent = 0.0
            payout = 0.0
            legs = []
            for a in acts:
                t_type = a.get("type")
                side = a.get("side", "BUY")
                outcome = a.get("outcome")
                sz = a.get("size")
                usd = float(a.get("usdcSize") or 0)
                px = float(a.get("price") or 0)
                if t_type == "TRADE":
                    if side == "BUY":
                        spent += usd
                        legs.append(f"{sz}sh {outcome} @ ${px:.2f}")
                    elif side == "SELL":
                        payout += usd
                        legs.append(f"SOLD {sz}sh {outcome} @ ${px:.2f}")
                elif t_type == "REDEEM":
                    payout += usd
            
            profit = round(payout - spent, 2)
            trades_list.append({
                "round": len(trades_list) + 1,
                "title": title,
                "legs": ", ".join(legs) if legs else "Pending",
                "spent": f"${spent:.2f}",
                "payout": f"${payout:.2f}" if payout > 0 else "Resolving",
                "profit": f"+${profit:.2f}" if payout > 0 else "Active",
                "status": "WON" if payout > 0 else "ACTIVE"
            })
        return list(reversed(trades_list))
    except Exception:
        return []

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Polybot · BTC 5M Wave Sniper</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-dark: #07090e;
            --card-bg: rgba(18, 24, 38, 0.85);
            --card-border: rgba(255, 255, 255, 0.07);
            --primary: #10b981;
            --primary-glow: rgba(16, 185, 129, 0.25);
            --accent: #38bdf8;
            --amber: #f59e0b;
            --rose: #f43f5e;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-dark);
            color: var(--text-main);
            font-family: 'Plus Jakarta Sans', sans-serif;
            min-height: 100vh;
            padding: 20px 16px 40px;
            background-image: 
                radial-gradient(circle at 15% 10%, rgba(16, 185, 129, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 85% 90%, rgba(56, 189, 248, 0.08) 0%, transparent 40%);
            background-attachment: fixed;
        }

        .container {
            max-width: 900px;
            margin: 0 auto;
        }

        /* Header */
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--card-border);
        }

        .logo-box {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo-badge {
            background: linear-gradient(135deg, #10b981, #059669);
            color: white;
            font-weight: 800;
            font-size: 14px;
            padding: 6px 10px;
            border-radius: 8px;
            box-shadow: 0 0 15px var(--primary-glow);
        }

        h1 {
            font-size: 20px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }

        .status-pill {
            display: flex;
            align-items: center;
            gap: 8px;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: #10b981;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
        }

        .pulse-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #10b981;
            box-shadow: 0 0 8px #10b981;
            animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
            0% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.4; transform: scale(1.2); }
            100% { opacity: 1; transform: scale(1); }
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 14px;
            margin-bottom: 24px;
        }

        .card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 18px;
            backdrop-filter: blur(12px);
            transition: transform 0.2s, border-color 0.2s;
        }

        .card:hover {
            border-color: rgba(255, 255, 255, 0.15);
            transform: translateY(-2px);
        }

        .card-label {
            font-size: 12px;
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }

        .card-val {
            font-size: 26px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        }

        .card-sub {
            font-size: 12px;
            margin-top: 4px;
            color: var(--text-muted);
        }

        .val-green { color: #10b981; }
        .val-cyan { color: #38bdf8; }
        .val-gold { color: #f59e0b; }

        /* Candle Section */
        .candle-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 20px;
            margin-bottom: 24px;
        }

        .candle-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }

        .market-title {
            font-size: 15px;
            font-weight: 600;
            color: var(--text-main);
        }

        .time-badge {
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            background: rgba(255, 255, 255, 0.05);
            padding: 4px 10px;
            border-radius: 6px;
            border: 1px solid var(--card-border);
        }

        .progress-bar-bg {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            height: 10px;
            overflow: hidden;
            position: relative;
            margin-bottom: 12px;
        }

        .progress-bar-fill {
            background: linear-gradient(90deg, #38bdf8, #10b981);
            height: 100%;
            width: 0%;
            border-radius: 10px;
            transition: width 0.5s ease;
        }

        .target-marker {
            position: absolute;
            left: 66.6%; /* 200s / 300s */
            top: 0;
            bottom: 0;
            width: 2px;
            background: #f59e0b;
            box-shadow: 0 0 6px #f59e0b;
        }

        .progress-labels {
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            color: var(--text-muted);
            font-family: 'JetBrains Mono', monospace;
        }

        /* Order Book Live Banner */
        .book-row {
            display: flex;
            gap: 12px;
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid var(--card-border);
        }

        .book-chip {
            flex: 1;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .book-chip span { font-size: 13px; color: var(--text-muted); }
        .book-chip strong { font-size: 16px; font-family: 'JetBrains Mono', monospace; }

        /* Trades Table */
        .table-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 20px;
        }

        .table-title {
            font-size: 16px;
            font-weight: 700;
            margin-bottom: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }

        th {
            text-align: left;
            padding: 10px 12px;
            color: var(--text-muted);
            font-weight: 600;
            border-bottom: 1px solid var(--card-border);
            font-size: 11px;
            text-transform: uppercase;
        }

        td {
            padding: 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.03);
        }

        .badge-win {
            background: rgba(16, 185, 129, 0.15);
            color: #10b981;
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 11px;
            font-family: 'JetBrains Mono', monospace;
        }

        .badge-active {
            background: rgba(56, 189, 248, 0.15);
            color: #38bdf8;
            padding: 3px 8px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 11px;
            font-family: 'JetBrains Mono', monospace;
        }

        .profit-pos {
            color: #10b981;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        }

        /* Refresh notice */
        .footer-note {
            text-align: center;
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 24px;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            <div class="logo-box">
                <div class="logo-badge">5M</div>
                <div>
                    <h1>Polybot Sniper</h1>
                    <div style="font-size: 12px; color: var(--text-muted);">Hedged Rollover Compounder</div>
                </div>
            </div>
            <div class="status-pill">
                <div class="pulse-dot" id="pulse-dot"></div>
                <span id="bot-status">HUNTING</span>
            </div>
        </header>

        <!-- Stats Grid -->
        <div class="stats-grid">
            <div class="card">
                <div class="card-label">USDC Cash Balance</div>
                <div class="card-val val-green" id="usdc-balance">$11.49</div>
                <div class="card-sub">Liquid in Polygon Wallet</div>
            </div>
            <div class="card">
                <div class="card-label">Streak Record</div>
                <div class="card-val val-cyan" id="streak-count">6 Wins</div>
                <div class="card-sub">100% Win Rate</div>
            </div>
            <div class="card">
                <div class="card-label">Total Profit Banked</div>
                <div class="card-val val-gold" id="total-profit">+$1.62</div>
                <div class="card-sub">Compounding Stake Active</div>
            </div>
            <div class="card">
                <div class="card-label">BTC Spot & Move</div>
                <div class="card-val" id="btc-move" style="font-size: 20px;">+$0.0</div>
                <div class="card-sub" id="btc-spot">BTC: $0</div>
            </div>
        </div>

        <!-- Active Candle Progress -->
        <div class="candle-card">
            <div class="candle-header">
                <div class="market-title" id="market-title">Loading active candle...</div>
                <div class="time-badge" id="time-badge">T-300s</div>
            </div>
            <div class="progress-bar-bg">
                <div class="target-marker" title="Trigger Zone (T+200s)"></div>
                <div class="progress-bar-fill" id="progress-fill"></div>
            </div>
            <div class="progress-labels">
                <span>0s (Open)</span>
                <span style="color: #f59e0b;">Target Zone: 200s (3.5 min)</span>
                <span>300s (Close)</span>
            </div>

            <div class="book-row">
                <div class="book-chip">
                    <span>UP Ask</span>
                    <strong class="val-cyan" id="up-ask">$1.00</strong>
                </div>
                <div class="book-chip">
                    <span>DOWN Ask</span>
                    <strong class="val-rose" id="down-ask" style="color: #f43f5e;">$1.00</strong>
                </div>
                <div class="book-chip">
                    <span>Active Stake</span>
                    <strong id="active-stake">5.0 sh</strong>
                </div>
            </div>
        </div>

        <!-- Recent Trades Table -->
        <div class="table-card">
            <div class="table-title">
                <span>Recent Arbitrage Rounds</span>
                <span style="font-size: 12px; font-weight: 500; color: var(--text-muted);">Auto-refreshed live</span>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Round</th>
                        <th>Market</th>
                        <th>Position Filled</th>
                        <th>Cost</th>
                        <th>Payout</th>
                        <th>Net Profit</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="trades-tbody">
                    <tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 20px;">Loading trade history...</td></tr>
                </tbody>
            </table>
        </div>

        <div class="footer-note">
            ⚡ Running 24/7 on Fly.io Cloud · Auto-polling every 1.5s
        </div>
    </div>

    <script>
        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const d = await res.json();

                document.getElementById('bot-status').innerText = d.status || 'HUNTING';
                document.getElementById('usdc-balance').innerText = '$' + (d.usdc_balance || 0).toFixed(2);
                document.getElementById('streak-count').innerText = (d.streak_count || 0) + ' Wins';
                document.getElementById('total-profit').innerText = '+' + (d.total_streak_profit || 0).toFixed(2) + ' USDC';
                
                const moveSign = (d.btc_move >= 0) ? '+' : '';
                document.getElementById('btc-move').innerText = moveSign + '$' + (d.btc_move || 0).toFixed(1);
                document.getElementById('btc-move').style.color = (d.btc_move >= 0) ? '#10b981' : '#f43f5e';
                document.getElementById('btc-spot').innerText = 'BTC: $' + (d.btc_spot || 0).toLocaleString();

                document.getElementById('market-title').innerText = d.market_title || 'Active BTC 5M';
                document.getElementById('time-badge').innerText = 'T-' + (d.t_rem || 0) + 's (Elapsed: ' + (d.t_elapsed || 0) + 's)';

                const pct = Math.min(100, Math.max(0, ((d.t_elapsed || 0) / 300) * 100));
                document.getElementById('progress-fill').style.width = pct + '%';

                document.getElementById('up-ask').innerText = '$' + (d.up_ask || 1.0).toFixed(2);
                document.getElementById('down-ask').innerText = '$' + (d.down_ask || 1.0).toFixed(2);
                document.getElementById('active-stake').innerText = (d.active_shares || 5).toFixed(0) + ' sh';

                // Status pill color
                const dot = document.getElementById('pulse-dot');
                if (d.status === 'HEDGED') {
                    dot.style.background = '#38bdf8';
                    dot.style.boxShadow = '0 0 8px #38bdf8';
                } else if (d.status === 'SETTLING') {
                    dot.style.background = '#f59e0b';
                    dot.style.boxShadow = '0 0 8px #f59e0b';
                } else {
                    dot.style.background = '#10b981';
                    dot.style.boxShadow = '0 0 8px #10b981';
                }

                // Render trades table
                if (d.trades && d.trades.length > 0) {
                    const tbody = document.getElementById('trades-tbody');
                    tbody.innerHTML = d.trades.map(t => `
                        <tr>
                            <td style="font-family: 'JetBrains Mono', monospace; font-weight: 600;">#${t.round}</td>
                            <td style="max-width: 220px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${t.title}</td>
                            <td style="font-family: 'JetBrains Mono', monospace; font-size: 12px;">${t.legs}</td>
                            <td style="font-family: 'JetBrains Mono', monospace;">${t.spent}</td>
                            <td style="font-family: 'JetBrains Mono', monospace;">${t.payout}</td>
                            <td class="profit-pos">${t.profit}</td>
                            <td><span class="${t.status === 'WON' ? 'badge-win' : 'badge-active'}">${t.status}</span></td>
                        </tr>
                    `).join('');
                }
            } catch(e) {
                console.error('Status fetch error:', e);
            }
        }

        setInterval(fetchStatus, 1500);
        fetchStatus();
    </script>
</body>
</html>
"""
class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        clean_path = self.path.split("?")[0]
        if clean_path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            # Attach recent trades
            out = dict(live_state)
            out["trades"] = get_recent_trades_from_api()
            self.wfile.write(json.dumps(out).encode("utf-8"))
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Keep console silent

def start_dashboard(port=8080):
    try:
        server = socketserver.TCPServer(("0.0.0.0", port), DashboardHandler)
        server.allow_reuse_address = True
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        print(f"📊 [DASHBOARD ACTIVE] Live web UI serving at http://0.0.0.0:{port}", flush=True)
        return server
    except Exception as e:
        print(f"⚠️ Dashboard server warning: {e}", flush=True)
        return None
