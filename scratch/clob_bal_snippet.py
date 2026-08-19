# State
pk = os.getenv("POLYMARKET_PRIVATE_KEY") or os.getenv("PRIVATE_KEY")
sig_type = int(os.getenv("SIGNATURE_TYPE", "3"))
funder = os.getenv("POLYMARKET_ADDRESS") or os.getenv("FUNDER_ADDRESS")

bot_state = {
    "name": "Bot Option A (Buy 0.98 -> Sell 0.99 Flip)",
    "status": "Initializing",
    "mode": "LIVE" if pk else "PAPER TRADING",
    "current_slug": None,
    "ptb": None,
    "btc_price": None,
    "delta": None,
    "up_ask": None,
    "down_ask": None,
    "up_size": 0.0,
    "down_size": 0.0,
    "balance": 0.0,
    "total_trades": 0,
    "total_profit_usdc": 0.0,
    "active_position": None,
    "logs": [],
    "history": []
}

log_lock = threading.Lock()
def log(msg):
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    entry = f"[{ts}] {msg}"
    print(entry, flush=True)
    with log_lock:
        bot_state["logs"].append(entry)
        if len(bot_state["logs"]) > 250:
            bot_state["logs"].pop(0)

# Import CLOB client
ClobClient = None
BalanceAllowanceParams = None
AssetType = None

try:
    from py_clob_client_v2.client import ClobClient
    from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType, OrderArgs, OrderType
    from py_clob_client_v2.order_builder.constants import BUY, SELL
except ImportError:
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import BalanceAllowanceParams, AssetType, OrderArgs, OrderType
        from py_clob_client.order_builder.constants import BUY, SELL
    except ImportError:
        pass

# CLOB Client Setup
client = None
if pk and ClobClient is not None:
    try:
        client = ClobClient(
            host="https://clob.polymarket.com",
            key=pk,
            chain_id=137,
            signature_type=sig_type,
            funder=funder
        )
        api_creds = client.create_or_derive_api_creds()
        client.set_api_creds(api_creds)
        log(f"[AUTH] Authenticated in LIVE mode with Polymarket CLOB. Proxy: {funder}")
    except Exception as e:
        log(f"[AUTH ERROR] Failed to initialize CLOB client: {e}")
        client = None

def get_real_wallet_balance():
    if client is not None and BalanceAllowanceParams is not None:
        try:
            params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
            resp = client.get_balance_allowance(params)
            log(f"[CLOB BALANCE RAW] {resp}")
            raw_bal = float(resp.get("balance", 0))
            return raw_bal / 1_000_000.0
        except Exception as e:
            log(f"[CLOB BALANCE ERROR] {e}")
    if not funder:
        return 0.0
    try:
        rpc_url = "https://polygon-rpc.com"
        usdc_e = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
        usdc_native = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
        padded = funder.lower().replace("0x", "").zfill(64)
        data = "0x70a08231" + padded
        
        total = 0.0
        for c in (usdc_e, usdc_native):
            payload = {"jsonrpc":"2.0","method":"eth_call","params":[{"to": c, "data": data}, "latest"],"id":1}
            r = requests.post(rpc_url, json=payload, timeout=3).json()
            if "result" in r and r["result"] != "0x":
                total += int(r["result"], 16) / 1e6
        return total
    except Exception:
        return bot_state.get("balance", 0.0)
