#!/usr/bin/env python3
"""
backtest_momentum_signal.py
----------------------------------------------------------------------------
Tests the "big move away from PTB = signal" idea against REAL historical
data, instead of guessing.

Dataset: aliplayer1/polymarket-crypto-updown (Hugging Face)
  - markets:      one row per market (start_ts, end_ts, resolution: 1=Up,0=Down)
  - spot_prices:  second-by-second Binance + Chainlink BTC/USD prices

Rule being tested:
    At T-{mark}s before close, look at (current_price - PTB) = move.
    If move >= +threshold  -> bet UP
    If move <= -threshold  -> bet DOWN
    Otherwise               -> no signal, skip

We sweep several `mark` values and `threshold` values and report the
REAL win rate + sample size for each combination, plus the baseline
(what "always bet UP" or "always bet DOWN" would get you, since ANY
useful signal has to beat that, not just beat 50%).

SETUP (run this on your own machine, not in a restricted sandbox):
    pip install duckdb

USAGE:
    python backtest_momentum_signal.py

NOTE: This script has NOT been executed by Claude — Hugging Face isn't
reachable from the sandbox Claude runs in. Please run it yourself and
paste the printed table back if you want help interpreting it or tuning
the live bot from the results.
----------------------------------------------------------------------------
"""

import duckdb

MARKS_TO_TEST       = [80, 70, 60, 50, 40, 30, 20, 10]      # seconds before close
THRESHOLDS_TO_TEST  = [10, 20, 30, 50, 75, 100, 150, 200]   # dollars
MIN_SAMPLE_SIZE     = 30   # don't trust a "win rate" backed by fewer signals than this

MARKETS_URL = "hf://datasets/aliplayer1/polymarket-crypto-updown/data/markets.parquet"
SPOT_URL    = "hf://datasets/aliplayer1/polymarket-crypto-updown/data/spot_prices/**/*.parquet"


def main():
    con = duckdb.connect()

    print("Loading markets + spot price data (this can take a bit on first run)...")

    # ── Base tables ──────────────────────────────────────────────────────
    con.execute(f"""
        CREATE TEMP TABLE mkts AS
        SELECT market_id, start_ts, end_ts, resolution
        FROM '{MARKETS_URL}'
        WHERE crypto = 'BTC' AND timeframe = '5-minute' AND resolution IN (0, 1)
    """)

    con.execute(f"""
        CREATE TEMP TABLE spot AS
        SELECT ts_ms / 1000.0 AS ts, price
        FROM '{SPOT_URL}'
        WHERE source = 'chainlink' AND symbol = 'btc/usd'
        ORDER BY ts
    """)

    n_markets = con.execute("SELECT COUNT(*) FROM mkts").fetchone()[0]
    n_spot    = con.execute("SELECT COUNT(*) FROM spot").fetchone()[0]
    print(f"Loaded {n_markets:,} BTC 5-min markets and {n_spot:,} chainlink spot ticks.\n")

    if n_markets == 0 or n_spot == 0:
        print("No data loaded — check that the dataset/columns still match this script.")
        return

    # ── Baseline: how often does UP actually win overall? ────────────────
    up_rate = con.execute("SELECT AVG(CAST(resolution AS DOUBLE)) FROM mkts").fetchone()[0]
    print(f"Baseline: UP wins {up_rate:.1%} of all 5-min BTC windows "
          f"(a 'no-info' coin flip would be 50.0%).\n")

    # ── PTB: first spot price at/after start_ts, per market ──────────────
    con.execute("""
        CREATE TEMP TABLE with_ptb AS
        SELECT m.market_id, m.start_ts, m.end_ts, m.resolution, s.price AS ptb
        FROM mkts m
        ASOF JOIN spot s ON s.ts >= m.start_ts
    """)

    results = []

    for mark in MARKS_TO_TEST:
        # Price at T-{mark}s before close = last spot tick at/before (end_ts - mark)
        con.execute(f"""
            CREATE OR REPLACE TEMP TABLE with_mark AS
            SELECT w.market_id, w.resolution, w.ptb, s.price AS price_at_mark
            FROM with_ptb w
            ASOF JOIN spot s ON s.ts <= (w.end_ts - {mark})
        """)

        for threshold in THRESHOLDS_TO_TEST:
            row = con.execute(f"""
                WITH scored AS (
                    SELECT
                        resolution,
                        (price_at_mark - ptb) AS move,
                        CASE
                            WHEN (price_at_mark - ptb) >= {threshold} THEN 'UP'
                            WHEN (price_at_mark - ptb) <= -{threshold} THEN 'DOWN'
                            ELSE NULL
                        END AS signal
                    FROM with_mark
                )
                SELECT
                    COUNT(*) FILTER (WHERE signal IS NOT NULL) AS n_signals,
                    AVG(
                        CASE
                            WHEN signal = 'UP'   AND resolution = 1 THEN 1.0
                            WHEN signal = 'DOWN' AND resolution = 0 THEN 1.0
                            WHEN signal IS NOT NULL THEN 0.0
                        END
                    ) FILTER (WHERE signal IS NOT NULL) AS win_rate
                FROM scored
            """).fetchone()

            n_signals, win_rate = row
            results.append((mark, threshold, n_signals or 0, win_rate))

    # ── Print results table ───────────────────────────────────────────────
    print(f"{'T-mark':>7}  {'$threshold':>10}  {'n_signals':>10}  {'win_rate':>9}  note")
    print("-" * 60)
    for mark, threshold, n_signals, win_rate in results:
        if n_signals == 0 or win_rate is None:
            print(f"T-{mark:>4}s  ${threshold:>8}  {n_signals:>10}  {'--':>9}  no signals fired")
            continue
        note = "" if n_signals >= MIN_SAMPLE_SIZE else "⚠ small sample, don't trust yet"
        print(f"T-{mark:>4}s  ${threshold:>8}  {n_signals:>10}  {win_rate:>8.1%}  {note}")

    print("\nHow to read this:")
    print(f" - Compare each win_rate to the baseline ({up_rate:.1%} for always-UP).")
    print(" - A real edge means win_rate is meaningfully ABOVE baseline AND has enough")
    print(f"   samples (n_signals >= {MIN_SAMPLE_SIZE}) to trust it, not just a lucky few rounds.")
    print(" - If nothing beats baseline by much, that's a real, useful answer too —")
    print("   it means this particular rule isn't adding real predictive value.")


if __name__ == "__main__":
    main()