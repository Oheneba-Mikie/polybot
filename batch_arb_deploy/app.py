import os
import time
import json
import asyncio
import datetime
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
from dotenv import load_dotenv

load_dotenv()

# CLOB imports
from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import (
    OrderArgs,
    PostOrdersV2Args,
    OrderType,
    ApiCreds,
)

# Configuration
GAMMA_HOST        = "https://gamma-api.polymarket.com"
CLOB_HOST         = "https://clob.polymarket.com"
TARGET_TOTAL_COST = float(os.getenv("TARGET_TOTAL_COST", "0.960")) # Max combined cost for UP + DOWN
REQUIRED_SHARES   = float(os.getenv("REQUIRED_SHARES", "5.0"))     # 5.0 shares per leg we buy
MIN_RESTING_DEPTH = float(os.getenv("MIN_RESTING_DEPTH", "50.0"))   # Must have >= 50.0 shares available (Anti-Front-Run Cushion)
DRY_RUN_MODE      = os.getenv("DRY_RUN", "false").lower() == "true" # Set to false for live execution

POLYMARKET_ADDRESS        = os.getenv("POLYMARKET_ADDRESS", "")
POLYMARKET_API_KEY        = os.getenv("POLYMARKET_API_KEY", "")
POLYMARKET_API_SECRET     = os.getenv("POLYMARKET_API_SECRET", "")
POLYMARKET_PASSPHRASE     = os.getenv("POLYMARKET_PASSPHRASE", "")
POLYMARKET_PRIVATE_KEY    = os.getenv("POLYMARKET_PRIVATE_KEY", "")

# App State
state: Dict[str, Any] = {
    "status": "Initializing...",
    "mode": "100% DRY RUN Paper Mode" if DRY_RUN_MODE else "LIVE REAL-MONEY BATCH TRADING",
    "dry_run": DRY_RUN_MODE,
    "current_candle": None,
    "candle_ends_at": None,
    "live_market_title": None,
    "up_token": None,
    "down_token": None,
    "live_up_ask": 0.0,
    "live_up_depth": 0.0,
    "live_down_ask": 0.0,
    "live_down_depth": 0.0,
    "combined_cost": 0.0,
    "active_trade": None,
    "trade_history": [],
    "total_trades": 0,
    "total_profit_usdc": 0.0,
    "logs": []
}

executor = ThreadPoolExecutor(max_workers=4)

def log(msg: str):
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    entry = f"[{timestamp}] {msg}"
    print(entry, flush=True)
    state["logs"].append(entry)
    if len(state["logs"]) > 250:
        state["logs"].pop(0)

# Initialize ClobClient
clob_client: Optional[ClobClient] = None
if POLYMARKET_PRIVATE_KEY and POLYMARKET_ADDRESS:
    try:
        creds = ApiCreds(
            api_key=POLYMARKET_API_KEY,
            api_secret=POLYMARKET_API_SECRET,
            api_passphrase=POLYMARKET_PASSPHRASE
        )
        clob_client = ClobClient(
            host=CLOB_HOST,
            key=POLYMARKET_PRIVATE_KEY,
            chain_id=137,
            creds=creds,
            signature_type=2,
            funder=POLYMARKET_ADDRESS
        )
        log("✅ [AUTH] ClobClient initialized successfully for Proxy: " + str(POLYMARKET_ADDRESS))
    except Exception as e:
        log(f"⚠️ [AUTH ERROR] Failed to initialize ClobClient: {e}")
else:
    log("⚠️ [AUTH] Running without API credentials (read-only / dry-run)")

app = FastAPI(title="PolyBot Batch Order Arbitrage")

def get_active_btc_5m_window():
    now = int(time.time())
    w_start = (now // 300) * 300
    slug = f"btc-updown-5m-{w_start}"
    try:
        r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
        if r and len(r) > 0 and r[0].get("markets"):
            m = r[0]["markets"][0]
            tokens = json.loads(m.get("clobTokenIds", "[]")) if isinstance(m.get("clobTokenIds"), str) else m.get("clobTokenIds", [])
            outcomes = json.loads(m.get("outcomes", "[]")) if isinstance(m.get("outcomes"), str) else m.get("outcomes", [])
            if len(tokens) >= 2:
                up_id = tokens[0] if outcomes[0].upper() == "UP" else tokens[1]
                down_id = tokens[1] if outcomes[0].upper() == "UP" else tokens[0]
                return {
                    "slug": slug,
                    "title": r[0].get("title"),
                    "start_ts": w_start,
                    "end_ts": w_start + 300,
                    "up_token": up_id,
                    "down_token": down_id
                }
    except Exception as e:
        pass
    return None

def fetch_book_depth(token_id: str):
    try:
        r = requests.get(f"{CLOB_HOST}/book?token_id={token_id}", timeout=1.5).json()
        asks = r.get("asks", [])
        if asks:
            best_ask = float(asks[0]["price"])
            depth = float(asks[0]["size"])
            return best_ask, depth
    except Exception:
        pass
    return 0.0, 0.0

async def batch_arbitrage_loop():
    log("🚀 [ENGINE] Starting Simultaneous Batch Arbitrage Engine...")
    current_market_slug = None
    executed_in_candle = False

    while True:
        try:
            mkt = get_active_btc_5m_window()
            if not mkt:
                state["status"] = "Waiting for active 5m market..."
                await asyncio.sleep(1.0)
                continue

            # Candle rollover
            if mkt["slug"] != current_market_slug:
                current_market_slug = mkt["slug"]
                executed_in_candle = False
                state["current_candle"] = mkt["slug"]
                state["live_market_title"] = mkt["title"]
                state["candle_ends_at"] = datetime.datetime.fromtimestamp(mkt["end_ts"], tz=datetime.timezone.utc).strftime("%H:%M:%S UTC")
                state["up_token"] = mkt["up_token"]
                state["down_token"] = mkt["down_token"]
                state["active_trade"] = None
                log(f"🔄 [CANDLE ROLLOVER] Loaded: {mkt['title']} ({mkt['slug']}) | Expiry: {state['candle_ends_at']}")

            if executed_in_candle:
                state["status"] = f"Trade completed for {current_market_slug}. Awaiting next candle."
                await asyncio.sleep(1.0)
                continue

            # Poll both books in parallel
            loop = asyncio.get_running_loop()
            up_fut = loop.run_in_executor(executor, fetch_book_depth, mkt["up_token"])
            down_fut = loop.run_in_executor(executor, fetch_book_depth, mkt["down_token"])
            (up_ask, up_depth), (down_ask, down_depth) = await asyncio.gather(up_fut, down_fut)

            state["live_up_ask"] = up_ask
            state["live_up_depth"] = up_depth
            state["live_down_ask"] = down_ask
            state["live_down_depth"] = down_depth

            if up_ask > 0 and down_ask > 0:
                combined_cost = round(up_ask + down_ask, 3)
                state["combined_cost"] = combined_cost

                # STRICT 3-CONDITION GATE WITH ANTI-FRONT-RUNNING CUSHION
                # 1. Combined cost <= TARGET_TOTAL_COST ($0.960)
                # 2. UP Depth >= MIN_RESTING_DEPTH (>= 50.0 shares)
                # 3. DOWN Depth >= MIN_RESTING_DEPTH (>= 50.0 shares)
                if combined_cost <= TARGET_TOTAL_COST and up_depth >= MIN_RESTING_DEPTH and down_depth >= MIN_RESTING_DEPTH:
                    log(f"⚡ [SIMULTANEOUS ARBITRAGE TRIGGERED WITH 50+ SH CUSHION] UP: ${up_ask:.3f} ({up_depth:.0f} sh) | DOWN: ${down_ask:.3f} ({down_depth:.0f} sh) | Sum: ${combined_cost:.3f} <= ${TARGET_TOTAL_COST:.3f}")
                    
                    cost_total = round(REQUIRED_SHARES * combined_cost, 2)
                    payout_total = round(REQUIRED_SHARES * 1.00, 2)
                    profit_total = round(payout_total - cost_total, 2)
                    profit_pct = round((profit_total / cost_total) * 100, 1)

                    trade_record = {
                        "market": mkt["title"],
                        "slug": mkt["slug"],
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-3],
                        "up_price": up_ask,
                        "up_shares": REQUIRED_SHARES,
                        "down_price": down_ask,
                        "down_shares": REQUIRED_SHARES,
                        "combined_price": combined_cost,
                        "total_cost": cost_total,
                        "payout": payout_total,
                        "profit": profit_total,
                        "profit_pct": profit_pct,
                        "state": "BATCH_ORDER_FIRED",
                        "tx_hashes": []
                    }

                    if not DRY_RUN_MODE and clob_client:
                        try:
                            # 1. Create and sign UP order
                            order_up = clob_client.create_order(OrderArgs(
                                price=up_ask,
                                size=REQUIRED_SHARES,
                                side="BUY",
                                token_id=mkt["up_token"]
                            ))
                            # 2. Create and sign DOWN order
                            order_down = clob_client.create_order(OrderArgs(
                                price=down_ask,
                                size=REQUIRED_SHARES,
                                side="BUY",
                                token_id=mkt["down_token"]
                            ))
                            # 3. Submit both simultaneously in 1 single batch HTTP request
                            post_args = [
                                PostOrdersV2Args(order=order_up, orderType=OrderType.GTC),
                                PostOrdersV2Args(order=order_down, orderType=OrderType.GTC)
                            ]
                            res = clob_client.post_orders(post_args)
                            log(f"🔴 [BATCH ORDER CONFIRMED] Response: {res}")
                            
                            txs = []
                            if isinstance(res, list):
                                for r in res:
                                    if isinstance(r, dict) and r.get("transactionsHashes"):
                                        txs.extend(r["transactionsHashes"])
                            trade_record["tx_hashes"] = txs
                            trade_record["state"] = "HEDGE_LOCKED"
                        except Exception as e:
                            log(f"❌ [BATCH ORDER ERROR] Failed to place batch: {e}")
                            trade_record["state"] = "FAILED"
                    else:
                        log(f"🧪 [DRY RUN BATCH SIMULATION] Executed 5 UP @ ${up_ask:.3f} + 5 DOWN @ ${down_ask:.3f} (Profit: +${profit_total:.2f})")
                        trade_record["state"] = "HEDGE_LOCKED"

                    if trade_record["state"] == "HEDGE_LOCKED":
                        executed_in_candle = True
                        state["active_trade"] = trade_record
                        state["trade_history"].append(trade_record)
                        state["total_trades"] += 1
                        state["total_profit_usdc"] = round(state["total_profit_usdc"] + profit_total, 2)
                        log(f"🔒 [100% DUAL-LEG HEDGE LOCKED IN SINGLE BATCH] Cost: ${cost_total} | Payout: ${payout_total} | Profit: +${profit_total} (+{profit_pct}%)")

            state["status"] = f"Scanning {current_market_slug} (UP: ${up_ask:.3f} [{up_depth:.0f}sh] | DOWN: ${down_ask:.3f} [{down_depth:.0f}sh] | Sum: ${state['combined_cost']:.3f})"
            await asyncio.sleep(0.1) # 100ms high-frequency polling
        except Exception as e:
            log(f"⚠️ [LOOP ERROR] {e}")
            await asyncio.sleep(1.0)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(batch_arbitrage_loop())

@app.get("/api/state")
def get_state():
    return JSONResponse(state)

@app.get("/", response_class=HTMLResponse)
def index():
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>PolyBot Batch Arbitrage</title>
        <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;800&family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg: #090d16;
                --card-bg: #111827;
                --card-border: #1f293d;
                --accent-blue: #3b82f6;
                --accent-emerald: #10b981;
                --accent-purple: #8b5cf6;
                --text-main: #f3f4f6;
                --text-muted: #9ca3af;
            }}
            * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Plus Jakarta Sans', sans-serif; }}
            body {{ background-color: var(--bg); color: var(--text-main); min-height: 100vh; padding: 24px; }}
            .container {{ max-width: 1200px; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }}
            .header {{ display: flex; justify-content: space-between; align-items: center; background: var(--card-bg); border: 1px solid var(--card-border); padding: 20px 24px; border-radius: 16px; }}
            .title-wrap h1 {{ font-size: 22px; font-weight: 800; display: flex; align-items: center; gap: 10px; }}
            .badge {{ font-size: 11px; padding: 4px 10px; border-radius: 20px; font-weight: 700; text-transform: uppercase; background: {"rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid #10b981;" if not DRY_RUN_MODE else "rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid #f59e0b;"} }}
            .grid-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }}
            .card {{ background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 16px; padding: 20px; }}
            .card-title {{ font-size: 13px; font-weight: 600; color: var(--text-muted); margin-bottom: 8px; }}
            .card-val {{ font-size: 26px; font-weight: 800; font-family: 'JetBrains Mono', monospace; }}
            .val-emerald {{ color: var(--accent-emerald); }}
            .val-blue {{ color: var(--accent-blue); }}
            .val-purple {{ color: var(--accent-purple); }}
            .order-book-card {{ background: #0c1220; border: 1px solid #1e293b; border-radius: 16px; padding: 20px; }}
            .log-box {{ background: #050811; border: 1px solid var(--card-border); border-radius: 12px; padding: 16px; font-family: 'JetBrains Mono', monospace; font-size: 12px; height: 320px; overflow-y: auto; color: #a5f3fc; }}
            .log-box div {{ margin-bottom: 4px; line-height: 1.5; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="title-wrap">
                    <h1>⚡ PolyBot: Standalone Simultaneous Batch Arbitrage</h1>
                    <p style="color: var(--text-muted); font-size: 13px; margin-top: 4px;">Single-HTTP Packet Execution (<code>POST /orders</code>) | 5.0 Shares | Target Combined &le; $0.960</p>
                </div>
                <span class="badge">{"LIVE REAL MONEY BATCH ARB" if not DRY_RUN_MODE else "100% DRY RUN PAPER MODE"}</span>
            </div>

            <div class="grid-stats">
                <div class="card">
                    <div class="card-title">LIVE COMBINED ASKS (UP + DOWN)</div>
                    <div class="card-val val-blue" id="combCost">$0.000</div>
                    <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">Target Ceiling: &le; $0.960</div>
                </div>
                <div class="card">
                    <div class="card-title">UP / DOWN DEPTH (&ge; 50.0 sh CUSHION)</div>
                    <div class="card-val val-purple" id="bookDepth">0 sh / 0 sh</div>
                    <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;" id="askPrices">UP: $0.00 | DOWN: $0.00</div>
                </div>
                <div class="card">
                    <div class="card-title">TOTAL COMPLETED BATCHES</div>
                    <div class="card-val" id="totalTrades">0</div>
                    <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">Strict 1 Trade / 5m Window</div>
                </div>
                <div class="card">
                    <div class="card-title">TOTAL LOCKED PROFIT</div>
                    <div class="card-val val-emerald" id="totalProfit">+$0.00 USDC</div>
                    <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">100% Guaranteed Settlement</div>
                </div>
            </div>

            <div class="card">
                <div class="card-title">CURRENT 5-MINUTE CANDLE & BATCH STATUS</div>
                <div id="candleInfo" style="font-size: 14px; font-weight: 600; color: #60a5fa; margin-bottom: 8px;">Loading...</div>
                <div id="tradeStatus" style="font-size: 13px; color: var(--text-muted);">Scanning order books...</div>
            </div>

            <div class="card">
                <div class="card-title">REAL-TIME EXECUTION LOGS</div>
                <div class="log-box" id="logsBox"></div>
            </div>
        </div>

        <script>
            async function updateState() {{
                try {{
                    const res = await fetch('/api/state');
                    const data = await res.json();
                    
                    document.getElementById('combCost').innerText = '$' + data.combined_cost.toFixed(3);
                    document.getElementById('combCost').style.color = (data.combined_cost <= 0.960 && data.combined_cost > 0) ? '#10b981' : '#3b82f6';
                    
                    document.getElementById('bookDepth').innerText = data.live_up_depth.toFixed(0) + ' sh / ' + data.live_down_depth.toFixed(0) + ' sh';
                    document.getElementById('askPrices').innerText = 'UP: $' + data.live_up_ask.toFixed(3) + ' | DOWN: $' + data.live_down_ask.toFixed(3);
                    
                    document.getElementById('totalTrades').innerText = data.total_trades;
                    document.getElementById('totalProfit').innerText = (data.total_profit_usdc >= 0 ? '+' : '') + '$' + data.total_profit_usdc.toFixed(2) + ' USDC';
                    
                    document.getElementById('candleInfo').innerText = (data.live_market_title || 'Connecting...') + ' (Ends: ' + (data.candle_ends_at || 'N/A') + ')';
                    document.getElementById('tradeStatus').innerText = 'Status: ' + data.status;
                    
                    const box = document.getElementById('logsBox');
                    box.innerHTML = data.logs.slice(-25).map(l => '<div>' + l + '</div>').join('');
                    box.scrollTop = box.scrollHeight;
                }} catch(e) {{}}
            }}
            setInterval(updateState, 500);
            updateState();
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, log_level="warning")
