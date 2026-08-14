import os
import sys
import json
import time
import datetime
import requests
from dotenv import load_dotenv

# Load env
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
load_dotenv(env_path)

POLYMARKET_ADDRESS = os.getenv("POLYMARKET_ADDRESS")
POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY")
POLYMARKET_API_SECRET = os.getenv("POLYMARKET_API_SECRET")
POLYMARKET_API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE")
POLYMARKET_PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY")

CLOB_HOST = "https://clob.polymarket.com"

def get_market_details_clob(market_hash):
    try:
        r = requests.get(f"{CLOB_HOST}/markets/{market_hash}", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def main():
    if not all([POLYMARKET_ADDRESS, POLYMARKET_API_KEY, POLYMARKET_API_SECRET, POLYMARKET_API_PASSPHRASE, POLYMARKET_PRIVATE_KEY]):
        print("Error: Missing Polymarket credentials in .env.")
        sys.exit(1)

    try:
        from py_clob_client_v2 import ClobClient, ApiCreds
        from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType, TradeParams
        from eth_account import Account
    except ImportError as e:
        print(f"Error importing clob client: {e}")
        sys.exit(1)

    eoa_address = Account.from_key(POLYMARKET_PRIVATE_KEY).address
    sig_type = 0
    funder_addr = None
    if POLYMARKET_ADDRESS and POLYMARKET_ADDRESS.lower() != eoa_address.lower():
        sig_type = 3
        funder_addr = POLYMARKET_ADDRESS

    creds = ApiCreds(
        api_key=POLYMARKET_API_KEY,
        api_secret=POLYMARKET_API_SECRET,
        api_passphrase=POLYMARKET_API_PASSPHRASE
    )
    clob_client = ClobClient(
        host=CLOB_HOST, chain_id=137, key=POLYMARKET_PRIVATE_KEY, creds=creds, signature_type=sig_type, funder=funder_addr
    )

    # Get balance
    print("Checking live balance...")
    params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
    resp = clob_client.get_balance_allowance(params)
    raw_bal = float(resp.get("balance", 0))
    bal = raw_bal / 1_000_000.0
    print(f"Current live balance: ${bal:.2f} USDC\n")

    # Get trades
    print("Fetching recent trades...")
    t_params = TradeParams(maker_address=POLYMARKET_ADDRESS)
    trades = clob_client.get_trades(t_params)
    if not trades:
        print("No trades found.")
        return

    # Filter for trades today (August 9, 2026)
    today_date = datetime.date(2026, 8, 9)
    today_trades = []
    for t in trades:
        match_time = int(float(t.get("match_time", 0)))
        trade_dt = datetime.datetime.fromtimestamp(match_time, tz=datetime.timezone.utc)
        if trade_dt.date() == today_date:
            today_trades.append(t)

    print(f"Found {len(today_trades)} trades matching August 9, 2026 (UTC).\n")
    if not today_trades:
        print("No trades today.")
        return

    # Group today's trades by market ID (the active market hash)
    market_trades = {}
    for t in today_trades:
        mkt_id = t.get("market")
        if mkt_id not in market_trades:
            market_trades[mkt_id] = []
        market_trades[mkt_id].append(t)

    # Print summary per market
    realized_pnl = 0
    total_wins = 0
    total_losses = 0
    total_pending = 0

    print("=" * 80)
    print(f"TRADES FOR TODAY: {today_date}")
    print("=" * 80)

    for mkt_id, t_list in market_trades.items():
        m_details = get_market_details_clob(mkt_id)
        q_text = m_details.get("question", mkt_id) if m_details else mkt_id
        slug = m_details.get("market_slug", "Unknown slug") if m_details else "Unknown slug"
        print(f"\nMarket: {q_text}")
        print(f"ID: {mkt_id} | Slug: {slug}")
        
        # Sort by match time ascending
        t_list.sort(key=lambda x: int(float(x.get("match_time", 0))))
        
        m_cost = 0
        shares_held = 0
        held_outcome = None
        
        for t in t_list:
            time_str = datetime.datetime.fromtimestamp(int(float(t.get("match_time"))), tz=datetime.timezone.utc).strftime("%H:%M:%S")
            side = t.get("side")
            size = float(t.get("size"))
            price = float(t.get("price"))
            val = size * price
            outcome = t.get("outcome")
            
            print(f"  [{time_str} UTC] {side} {size:.4f} {outcome} shares @ ${price:.4f} (Cost: ${val:.4f})")
            
            if side == "BUY":
                shares_held += size
                m_cost += val
                held_outcome = outcome
            else:
                shares_held -= size
                m_cost -= val

        # Check resolution
        if shares_held > 0.01:
            resolved = False
            winner_outcome = None
            if m_details:
                tokens = m_details.get("tokens", [])
                closed = m_details.get("closed", False)
                # Check if winner is set on any token
                has_winner = any(tok.get("winner") is not None for tok in tokens)
                if closed or has_winner:
                    resolved = True
                    for tok in tokens:
                        if tok.get("winner") is True or tok.get("price") == 1:
                            winner_outcome = tok.get("outcome")
                            break

            if resolved and winner_outcome:
                is_win = (held_outcome.lower() == winner_outcome.lower())
                payout = shares_held * 1.0 if is_win else 0.0
                m_pnl = payout - m_cost
                realized_pnl += m_pnl
                
                if is_win:
                    total_wins += 1
                    status_str = f"WIN (Winning Outcome: {winner_outcome})"
                else:
                    total_losses += 1
                    status_str = f"LOSS (Winning Outcome: {winner_outcome})"
                
                print(f"  -> {status_str} | PnL: ${m_pnl:+.4f} USDC (Staked: ${m_cost:.4f}, Returned: ${payout:.4f})")
            else:
                total_pending += 1
                print(f"  -> PENDING / UNRESOLVED | Staked: ${m_cost:.4f} (Held {shares_held:.4f} {held_outcome})")
        else:
            # Scalped or closed
            m_pnl = -m_cost
            realized_pnl += m_pnl
            if m_pnl > 0:
                total_wins += 1
                status_str = "WIN (Closed)"
            else:
                total_losses += 1
                status_str = "LOSS (Closed)"
            print(f"  -> {status_str} | Realized PnL: ${m_pnl:+.4f} USDC")

    print("\n" + "="*80)
    print(f"SUMMARY FOR TODAY (August 9, 2026):")
    print(f"Wins: {total_wins}  |  Losses: {total_losses}  |  Pending: {total_pending}")
    print(f"Realized P&L: {realized_pnl:+.4f} USDC")
    print("="*80)

if __name__ == "__main__":
    main()
