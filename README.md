# polybot 🤖

Paper-trading bot for Polymarket BTC 5-minute Up/Down markets.

## Discovery

Through live testing we confirmed:
- **The closing price of window N = the Price to Beat for window N+1**
- Polymarket uses the **Chainlink BTC/USD price at the exact 5-minute boundary** as the reference
- The order book's UP/DOWN ask prices reflect real-time market probability
- **UP ask liquidity disappears at ~T-18s** before close (last safe bet: T-20s)

## Files

| File | Purpose |
|---|---|
| `smartbot.py` | **Main bot** — waits for window open, tracks Price to Beat, polls order book, bets on market-favored direction at T-20s |
| `polybot.py` | Original bot — WS-only price tracking with trigger-based strategy |
| `track_ws.py` | Live WS tracker — streams every Chainlink tick, auto-exits at window close |
| `test_bet_timing.py` | Empirically finds the last second you can bet before market closes |

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install requests websocket-client web3
```

## Usage

```bash
# Main bot (runs forever, paper trading)
python smartbot.py

# Watch one window and exit
python smartbot.py --cycles 1

# Observe only, no bets placed
python smartbot.py --dry-run

# Live WS price tracker (auto-exits at window close)
python track_ws.py

# Find the latest moment you can bet
python test_bet_timing.py

# Original bot
python polybot.py
python polybot.py --ws-price   # print current BTC price and exit
python polybot.py --status     # print balance/mode
python polybot.py --reset      # reset to $100
```

## Strategy (smartbot.py)

1. Wait for window boundary (`:00` or `:05` mark)
2. Capture **Price to Beat** = first WS tick at window open
3. Stream Chainlink ticks, show live diff vs Price to Beat
4. From T-120s: poll order book every second
5. At **T-20s**: read UP ask vs DOWN ask — bet on the market favorite (higher ask = more confident)
6. Show window close summary + P&L

## Returns

| Entry price | Market confidence | Profit on $1 stake |
|---|---|---|
| $0.51 | 50/50 | +$0.96 |
| $0.81 | 81% | +$0.23 |
| $0.95 | 95% | +$0.05 |

> **Paper trading only** — no real orders are placed.
