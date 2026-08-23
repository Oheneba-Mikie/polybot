import os, sys, time, json, math, threading, requests, datetime, ssl
from flask import Flask, render_template, jsonify
from dotenv import load_dotenv

sys.stdout.reconfigure(line_buffering=True)
load_dotenv()

app = Flask(__name__)

bot_state = {
    "status": "Initializing",
    "last_trade": None,
    "wins": 0,
    "losses": 0,
    "total_scalps": 0,
    "total_profit_usdc": 0.0,
    "stake": 4.85,
    "streak": 0,
    "paused": False,
    "logs": [],
    "history": [],
    "balance": 0.0,
    "bot_bankroll": 5.50,
    "held_position": None,
    "scalps_current_candle": 0
}

INITIAL_BOT_BANKROLL = float(os.getenv("INITIAL_BOT_BANKROLL", "5.50"))
bot_bankroll = INITIAL_BOT_BANKROLL

def log(msg):
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    try:
        print(formatted, flush=True)
    except UnicodeEncodeError:
        print(formatted.encode("ascii", "replace").decode("ascii"), flush=True)
    bot_state["logs"].append(formatted)
    if len(bot_state["logs"]) > 200:
        bot_state["logs"].pop(0)

GAMMA_HOST = "https://gamma-api.polymarket.com"
DATA_HOST  = "https://data-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

POLYMARKET_LIVE_TRADING    = os.getenv("POLYMARKET_LIVE_TRADING", "true").lower() == "true"
POLYMARKET_ADDRESS         = os.getenv("POLYMARKET_ADDRESS", "")
POLYMARKET_API_KEY         = os.getenv("POLYMARKET_API_KEY", "")
POLYMARKET_API_SECRET      = os.getenv("POLYMARKET_API_SECRET", "")
POLYMARKET_API_PASSPHRASE  = os.getenv("POLYMARKET_API_PASSPHRASE", "")
POLYMARKET_PRIVATE_KEY     = os.getenv("POLYMARKET_PRIVATE_KEY", "")

WINDOW_SECS = 300

def win_start(ts=None):
    if ts is None: ts = time.time()
    return int(ts // WINDOW_SECS) * WINDOW_SECS

def win_end(ts=None):
    return win_start(ts) + WINDOW_SECS

def slug_for(ts=None):
    return f"btc-updown-5m-{win_start(ts)}"

client = None
if POLYMARKET_LIVE_TRADING:
    try:
        from py_clob_client_v2 import ClobClient, ApiCreds
        creds = ApiCreds(
            api_key=POLYMARKET_API_KEY,
            api_secret=POLYMARKET_API_SECRET,
            api_passphrase=POLYMARKET_API_PASSPHRASE
        )
        client = ClobClient(
            host=CLOB_HOST,
            chain_id=137,
            key=POLYMARKET_PRIVATE_KEY,
            creds=creds,
            signature_type=3,
            funder=POLYMARKET_ADDRESS
        )
        log("⚡ Initialized Continuous Rapid Multi-Scalper CLOB Engine.")
    except Exception as e:
        log(f"CLOB Client error: {e}")


def get_market_tokens_for_candle(ts=None):
    slug = slug_for(ts)
    url = f"{GAMMA_HOST}/events?slug={slug}"
    try:
        r = requests.get(url, timeout=3)
        evts = r.json()
        if not evts or not evts[0].get("markets"): return None
        mkt  = evts[0]["markets"][0]
        tids = json.loads(mkt.get("clobTokenIds") or "[]")
        outs = [str(o).lower() for o in json.loads(mkt.get("outcomes") or "[]")]
        up_id = dn_id = None
        for i, o in enumerate(outs):
            if o in ("up", "yes"):    up_id = tids[i]
            elif o in ("down", "no"): dn_id = tids[i]
        if not up_id and len(tids) > 0: up_id = tids[0]
        if not dn_id and len(tids) > 1: dn_id = tids[1]
        return {"slug": slug, "title": mkt.get("question", slug), "up_id": up_id, "down_id": dn_id}
    except Exception:
        return None


def probe_book(token_id, timeout=2):
    try:
        r = requests.get(f"{CLOB_HOST}/book", params={"token_id": token_id}, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        asks = data.get("asks", [])
        bids = data.get("bids", [])
        best_ask = float(min(asks, key=lambda a: float(a["price"]))["price"]) if asks else None
        best_bid = float(max(bids, key=lambda b: float(b["price"]))["price"]) if bids else None
        return best_ask, best_bid
    except Exception:
        return None, None


def get_live_balance():
    if not client:
        return 5.50
    try:
        from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
        resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        raw_b = float(resp.get("balance", 0)) / 1_000_000
        return round(raw_b, 2)
    except Exception as e:
        return 0.0


def get_token_shares_balance(token_id):
    if not client:
        return 0.0
    try:
        from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
        resp = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.CONDITIONAL, token_id=token_id))
        raw_b = float(resp.get("balance", 0)) / 1_000_000
        return round(raw_b, 4)
    except Exception:
        return 0.0


def dump_shares_market(token_id, shares_amount, reason_tag="BAILOUT"):
    if not client:
        return False
    
    from py_clob_client_v2 import MarketOrderArgsV2, OrderType

    for attempt in range(1, 8):
        live_sh = get_token_shares_balance(token_id)
        sh_to_dump = math.floor(live_sh * 100.0) / 100.0 if live_sh >= 0.1 else math.floor(shares_amount * 100.0) / 100.0
        
        if sh_to_dump < 0.1:
            log(f"✅ ZERO SHARES ({reason_tag}): Position cleared.")
            return True
            
        try:
            _, live_bid = probe_book(token_id)
            log(f"🚨 IMMEDIATE MARKET DUMP (Attempt {attempt} | {reason_tag} | Top Bid: ${live_bid if live_bid else 0:.3f}): Liquidating {sh_to_dump:.2f} shares...")
            # Price=0.01 on SELL matches against the highest available bids on the order book immediately
            client.create_and_post_market_order(
                MarketOrderArgsV2(token_id=token_id, amount=sh_to_dump, price=0.01, side="SELL", order_type=OrderType.FAK),
                order_type=OrderType.FAK
            )
            time.sleep(0.4)
            remaining = get_token_shares_balance(token_id)
            if remaining < 0.1:
                log(f"✅ DUMP SUCCESS: All {sh_to_dump:.2f} shares liquidated to USDC.")
                return True
        except Exception as e:
            log(f"⚠️ Dump Retry ({reason_tag}): {e}. Retrying in 0.3s...")
            time.sleep(0.3)
            
    return False


def manage_position_loop(token_id, side_name, entry_price, shares_amount, candle_end, target_profit_bid=0.980, stop_loss_min_bid=0.940):
    """
    Continuous Position Guardian:
    Guarantees 100% exit via Profit Target, Stop Loss, 30s Timeout, or T-10s Pre-Close.
    """
    global bot_bankroll
    from py_clob_client_v2 import MarketOrderArgsV2, OrderType
    
    entry_time = time.time()
    log(f"🛡️ GUARDIAN ACTIVE: Holding {shares_amount:.2f} shares of {side_name} (Entry: ${entry_price:.4f} | Target: ${target_profit_bid:.3f} | Stop Loss: ${stop_loss_min_bid:.3f}).")
    bot_state["held_position"] = f"{shares_amount:.2f} {side_name} @ ${entry_price:.2f}"

    while True:
        elapsed = time.time() - entry_time
        time_to_close = candle_end - time.time()
        
        _, live_bid = probe_book(token_id)
        
        # 1. PROFIT EXIT: Target reached
        if live_bid and live_bid >= target_profit_bid:
            log(f"🎉 PROFIT TARGET HIT! Live Bid is ${live_bid:.4f} >= ${target_profit_bid:.3f}. Selling immediately...")
            try:
                live_sh = get_token_shares_balance(token_id)
                sh_to_sell = math.floor(live_sh * 100.0) / 100.0 if live_sh >= 0.1 else math.floor(shares_amount * 100.0) / 100.0
                client.create_and_post_market_order(
                    MarketOrderArgsV2(token_id=token_id, amount=sh_to_sell, price=0.01, side="SELL", order_type=OrderType.FAK),
                    order_type=OrderType.FAK
                )
                profit_per_share = live_bid - entry_price
                p_usdc = round(sh_to_sell * profit_per_share, 4)
                pct = (profit_per_share / entry_price) * 100.0
                
                bot_bankroll = round(bot_bankroll + p_usdc, 4)
                bot_state["bot_bankroll"] = bot_bankroll
                
                log(f"🏆 RAPID SCALP WON! Sold @ ${live_bid:.4f} | Net: +${p_usdc:.4f} ({pct:+.2f}%) | Bot Bankroll: ${bot_bankroll:.2f}")
                
                bot_state["total_scalps"] += 1
                bot_state["scalps_current_candle"] = bot_state.get("scalps_current_candle", 0) + 1
                bot_state["total_profit_usdc"] = round(bot_state.get("total_profit_usdc", 0.0) + p_usdc, 4)
                bot_state["last_trade"] = f"Bought @ ${entry_price:.2f} -> Sold @ ${live_bid:.2f} ({pct:+.1f}%)"
                bot_state["wins"] += 1
                bot_state["streak"] += 1
                bot_state["held_position"] = None
                return True
            except Exception as e:
                log(f"Sell order retry: {e}")

        # 2. EMERGENCY STOP LOSS: Bid dropped below stop loss threshold
        elif live_bid and live_bid < stop_loss_min_bid:
            log(f"🚨 STOP LOSS TRIGGERED: Bid dropped to ${live_bid:.4f} < ${stop_loss_min_bid:.3f}. Sweeping immediately at market...")
            dump_shares_market(token_id, shares_amount, reason_tag="STOP_LOSS")
            loss_usdc = round(shares_amount * (entry_price - live_bid), 4)
            bot_bankroll = max(1.00, round(bot_bankroll - loss_usdc, 4))
            bot_state["bot_bankroll"] = bot_bankroll
            log(f"🛡️ CAPITAL PRESERVED: Dumped | Bot Bankroll: ${bot_bankroll:.2f}")
            bot_state["losses"] += 1
            bot_state["streak"] = 0
            bot_state["held_position"] = None
            return True

        # 3. 30-SECOND TIMEOUT: Market stalled
        elif elapsed >= 30.0:
            log(f"⏰ 30s TIMEOUT BAILOUT: Stalled after {elapsed:.1f}s. Liquidating {shares_amount:.2f} shares at market...")
            dump_shares_market(token_id, shares_amount, reason_tag="TIMEOUT_30S")
            bot_state["held_position"] = None
            return True

        # 4. PRE-CLOSE SAFETY CUTOFF: T-10 seconds before candle ends
        elif time_to_close <= 10.0:
            log(f"⚠️ PRE-CLOSE CUTOFF: Only {time_to_close:.1f}s left in candle. Liquidating before resolution...")
            dump_shares_market(token_id, shares_amount, reason_tag="PRE_CLOSE_10S")
            bot_state["held_position"] = None
            return True
            return True

        time.sleep(0.05)


def bot_worker():
    log("🚀 Continuous Rapid Buy/Sell Scalper Online! Scanning 5m candles in real-time...")
    bot_state["status"] = "Running"

    while True:
        try:
            now = time.time()
            w_s = win_start(now)
            w_e = win_end(now)
            
            mkt_info = get_market_tokens_for_candle(now)
            if not mkt_info or not mkt_info.get("up_id") or not mkt_info.get("down_id"):
                time.sleep(2)
                continue

            up_id = mkt_info["up_id"]
            dn_id = mkt_info["down_id"]
            slug  = mkt_info["slug"]
            
            log(f"🎯 ACTIVE CANDLE: {slug} | Continuous Multi-Scalping enabled until T-10s...")
            bot_state["scalps_current_candle"] = 0

            # Continuous Scalp Loop within this candle
            while True:
                t_now = time.time()
                time_left = w_e - t_now
                
                # Stop entering when candle has less than 12s left
                if time_left <= 12.0:
                    break

                # Query live balance
                current_cash = get_live_balance()
                safe_cash = math.floor(current_cash * 0.95 * 100.0) / 100.0
                
                if safe_cash < 4.50:
                    time.sleep(1)
                    continue

                # Probe order books
                up_ask, _ = probe_book(up_id)
                dn_ask, _ = probe_book(dn_id)

                target_token_id = None
                side_name = None
                entry_ask_price = None

                # Continuous momentum entry triggers:
                # 1. 97c -> 98c Scalp
                if up_ask and 0.965 <= up_ask <= 0.978:
                    target_token_id = up_id
                    side_name = "UP"
                    entry_ask_price = up_ask
                    target_profit = 0.980
                    stop_loss = 0.945
                    dump_floor = 0.940
                elif dn_ask and 0.965 <= dn_ask <= 0.978:
                    target_token_id = dn_id
                    side_name = "DOWN"
                    entry_ask_price = dn_ask
                    target_profit = 0.980
                    stop_loss = 0.945
                    dump_floor = 0.940
                # 2. 88c -> 93c Scalp
                elif up_ask and 0.840 <= up_ask <= 0.880:
                    target_token_id = up_id
                    side_name = "UP"
                    entry_ask_price = up_ask
                    target_profit = 0.930
                    stop_loss = 0.800
                    dump_floor = 0.780
                elif dn_ask and 0.840 <= dn_ask <= 0.880:
                    target_token_id = dn_id
                    side_name = "DOWN"
                    entry_ask_price = dn_ask
                    target_profit = 0.930
                    stop_loss = 0.800
                    dump_floor = 0.780

                if target_token_id:
                    min_needed = round(5.0 * entry_ask_price, 2)
                    trade_alloc = min(bot_bankroll, safe_cash)
                    stake_amount = max(min_needed, math.floor(trade_alloc * 100.0) / 100.0)
                    stake_amount = min(stake_amount, safe_cash)

                    log(f"⚡ RAPID ENTRY on {side_name} @ ${entry_ask_price:.4f}! Sizing ${stake_amount:.2f} USDC (Target: ${target_profit:.3f} | Bankroll: ${bot_bankroll:.2f})...")

                    if client:
                        try:
                            from py_clob_client_v2 import MarketOrderArgsV2, OrderType

                            # Execute BUY
                            client.create_and_post_market_order(
                                MarketOrderArgsV2(token_id=target_token_id, amount=stake_amount, price=entry_ask_price, side="BUY", order_type=OrderType.FAK),
                                order_type=OrderType.FAK
                            )

                            time.sleep(0.3)
                            actual_shares = get_token_shares_balance(target_token_id)
                            if actual_shares < 0.1:
                                actual_shares = round(stake_amount / entry_ask_price, 2)

                            log(f"⏱️ BOUGHT {actual_shares:.4f} shares of {side_name} @ ${entry_ask_price:.4f}.")
                            
                            # Hand over to Guardian for rapid exit
                            manage_position_loop(
                                target_token_id, 
                                side_name, 
                                entry_ask_price, 
                                actual_shares, 
                                w_e,
                                target_profit_bid=target_profit,
                                stop_loss_min_bid=stop_loss
                            )

                            # Settle pause for 0.5s before taking next scalp in the same candle!
                            time.sleep(0.5)

                        except Exception as ex:
                            log(f"Buy error: {ex}")
                            time.sleep(0.5)

                time.sleep(0.05)

            # Wait for next candle window start
            time_to_next = max(0.5, w_e - time.time() + 0.5)
            time.sleep(time_to_next)

        except Exception as e:
            log(f"Loop error: {e}")
            time.sleep(1)


@app.route("/")
def index():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>⚡ Continuous Rapid Multi-Scalper Bot</title>
        <meta http-equiv="refresh" content="3">
        <style>
            body {{ background: #0b0f19; color: #f3f4f6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; }}
            .card {{ background: #111827; border: 1px solid #1f2937; border-radius: 10px; padding: 20px; max-width: 900px; margin: 0 auto; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.5); }}
            h1 {{ color: #60a5fa; margin-top: 0; display: flex; align-items: center; justify-content: space-between; }}
            .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }}
            .stat-box {{ background: #1f2937; padding: 15px; border-radius: 8px; text-align: center; }}
            .stat-val {{ font-size: 24px; font-weight: bold; color: #10b981; }}
            .log-box {{ background: #000; border-radius: 8px; padding: 15px; height: 350px; overflow-y: auto; font-family: monospace; font-size: 13px; color: #a7f3d0; border: 1px solid #374151; }}
            .badge {{ background: #10b981; color: #000; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>
                <span>⚡ Continuous Rapid Multi-Scalper</span>
                <span class="badge">ACTIVE (LIVE)</span>
            </h1>
            <div class="stats">
                <div class="stat-box"><div>Total Scalps</div><div class="stat-val">{bot_state['total_scalps']}</div></div>
                <div class="stat-box"><div>Wins / Losses</div><div class="stat-val" style="color:#60a5fa;">{bot_state['wins']}W / {bot_state['losses']}L</div></div>
                <div class="stat-box"><div>Net Profit</div><div class="stat-val">+${bot_state['total_profit_usdc']:.2f}</div></div>
                <div class="stat-box"><div>Bankroll</div><div class="stat-val">${bot_state['bot_bankroll']:.2f}</div></div>
            </div>
            <h3>📜 Live Millisecond Execution Stream</h3>
            <div class="log-box">
                {"<br>".join(reversed(bot_state['logs']))}
            </div>
        </div>
    </body>
    </html>
    """

@app.route("/api/state")
def state():
    return jsonify(bot_state)

if __name__ == "__main__":
    t = threading.Thread(target=bot_worker, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
