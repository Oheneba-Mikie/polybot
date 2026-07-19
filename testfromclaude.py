#!/usr/bin/env python3
"""
backtest_orderbook_signal.py
----------------------------------------------------------------------------
Tests the ACTUAL rule the console alert tool uses:

    "Bet on whichever side's ask price is >= CONFIDENCE_THRESHOLD,
     and (in Section 2) only if that side has stayed the dominant/
     confident side for 2 probes in a row, and only if its price
     hasn't already run up past MAX_PRICE_CAP."

...against real historical Polymarket order-book + resolution data, so
you get an actual measured win rate instead of a guess.

Dataset: aliplayer1/polymarket-crypto-updown (Hugging Face)
  - markets:    one row per market (start_ts, end_ts, resolution, token ids)
  - orderbook:  best_bid/best_ask snapshots per token over time

SETUP (run on your own machine — Hugging Face isn't reachable from
Claude's sandbox, so this script has NOT been executed by Claude):
    pip install duckdb

USAGE:
    python backtest_orderbook_signal.py
----------------------------------------------------------------------------
"""

import os
import duckdb

MARKS_TO_TEST         = [80, 70, 60, 50, 40, 35, 30, 25, 20, 15, 10, 5]  # secs before close
CONFIDENCE_THRESHOLDS = [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
MIN_SAMPLE_SIZE       = 30

# Section 2: stability + price-cap combo, tested at these bet marks
STABILITY_BET_MARKS   = [30, 25, 20]
STABILITY_CONFIDENCE  = 0.65   # matches the console tool's CONFIDENCE_THRESHOLD
MAX_PRICE_CAP         = 0.95   # matches the console tool's MAX_PRICE_ALERT

MARKETS_URL   = "hf://datasets/aliplayer1/polymarket-crypto-updown/data/markets.parquet"
ORDERBOOK_URL = "hf://datasets/aliplayer1/polymarket-crypto-updown/data/orderbook/crypto=BTC/timeframe=5-minute/**/*.parquet"


def load_base_tables(con):
    print("Loading markets data...")
    con.execute("PRAGMA memory_limit='4GB'")
    con.execute("PRAGMA max_temp_directory_size='20GiB'")
    con.execute("SET preserve_insertion_order=false")

    con.execute(f"""
        CREATE TEMP TABLE mkts AS
        SELECT market_id, start_ts, end_ts, resolution, up_token_id, down_token_id
        FROM '{MARKETS_URL}'
        WHERE crypto = 'BTC' AND timeframe = '5-minute' AND resolution IN (0, 1)
    """)
    n_markets = con.execute("SELECT COUNT(*) FROM mkts").fetchone()[0]
    print(f"Loaded {n_markets:,} markets.\n")

    # ── Download order book data to LOCAL disk exactly once ────────────────
    # Earlier version queried the remote parquet files directly as a view,
    # which meant every single test (12 time marks x several sections) sent
    # a fresh HTTP request to Hugging Face -- that's what triggered the
    # "429 Too Many Requests" error. Downloading it once to a local file
    # means every later query reads from disk, with no more network calls.
    local_book_path = "book_cache.parquet"
    if not os.path.exists(local_book_path):
        print("Downloading order book data to local disk (one-time, may take a while)...")
        con.execute(f"""
            COPY (
                SELECT market_id, token_id, ts_ms, best_ask
                FROM '{ORDERBOOK_URL}'
                WHERE market_id IN (SELECT market_id FROM mkts)
            ) TO '{local_book_path}' (FORMAT PARQUET)
        """)
        print(f"Saved local copy: {local_book_path}\n")
    else:
        print(f"Using existing local copy: {local_book_path} "
              f"(delete this file if you want to re-download fresh data)\n")

    con.execute(f"""
        CREATE TEMP VIEW book AS
        SELECT * FROM '{local_book_path}'
    """)
    return n_markets


def asks_at_mark(con, mark):
    """Returns a temp table `asks_<mark>` with up_ask/down_ask per market at T-{mark}s."""
    tbl = f"asks_{mark}"
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE {tbl} AS
        WITH targets AS (
            SELECT market_id, resolution, up_token_id, down_token_id,
                   (end_ts - {mark}) * 1000 AS target_ms
            FROM mkts
        ),
        up_ask AS (
            SELECT t.market_id, b.best_ask AS up_ask
            FROM targets t
            ASOF JOIN book b
              ON b.market_id = t.market_id
             AND b.token_id  = t.up_token_id
             AND b.ts_ms    <= t.target_ms
        ),
        down_ask AS (
            SELECT t.market_id, b.best_ask AS down_ask
            FROM targets t
            ASOF JOIN book b
              ON b.market_id = t.market_id
             AND b.token_id  = t.down_token_id
             AND b.ts_ms    <= t.target_ms
        )
        SELECT t.market_id, t.resolution, u.up_ask, d.down_ask
        FROM targets t
        LEFT JOIN up_ask u   ON u.market_id = t.market_id
        LEFT JOIN down_ask d ON d.market_id = t.market_id
    """)
    return tbl


def section1_confidence_only(con, up_rate):
    print("=" * 72)
    print("SECTION 1: confidence-only rule (bet the dominant side if its ask")
    print("           crosses the threshold, no stability or price cap yet)")
    print("=" * 72)
    print(f"{'T-mark':>7}  {'confidence':>10}  {'n_signals':>10}  {'win_rate':>9}  note")
    print("-" * 66)

    for mark in MARKS_TO_TEST:
        tbl = asks_at_mark(con, mark)
        for conf in CONFIDENCE_THRESHOLDS:
            row = con.execute(f"""
                WITH scored AS (
                    SELECT
                        resolution,
                        CASE
                            WHEN up_ask IS NULL OR down_ask IS NULL THEN NULL
                            WHEN up_ask >= {conf} AND up_ask > down_ask THEN 'UP'
                            WHEN down_ask >= {conf} AND down_ask > up_ask THEN 'DOWN'
                            ELSE NULL
                        END AS signal
                    FROM {tbl}
                )
                SELECT
                    COUNT(*) FILTER (WHERE signal IS NOT NULL) AS n_signals,
                    AVG(CASE
                            WHEN signal = 'UP'   AND resolution = 1 THEN 1.0
                            WHEN signal = 'DOWN' AND resolution = 0 THEN 1.0
                            WHEN signal IS NOT NULL THEN 0.0
                        END) FILTER (WHERE signal IS NOT NULL) AS win_rate
                FROM scored
            """).fetchone()
            n_signals, win_rate = row
            if not n_signals:
                print(f"T-{mark:>4}s  {conf:>10.0%}  {n_signals or 0:>10}  {'--':>9}  no signals")
                continue
            note = "" if n_signals >= MIN_SAMPLE_SIZE else "small sample"
            beat = "  (beats baseline)" if win_rate > up_rate + 0.02 else ""
            print(f"T-{mark:>4}s  {conf:>10.0%}  {n_signals:>10}  {win_rate:>8.1%}  {note}{beat}")


def section2_stability_and_cap(con, up_rate):
    print()
    print("=" * 72)
    print("SECTION 2: confidence + STABILITY (signal held 2 probes in a row)")
    print(f"           + price cap (skip if ask > {MAX_PRICE_CAP:.0%})")
    print("           -- this mirrors the console alert tool's actual logic")
    print("=" * 72)
    print(f"{'bet mark':>9}  {'n_signals':>10}  {'win_rate':>9}  note")
    print("-" * 50)

    for mark in STABILITY_BET_MARKS:
        earlier_mark = mark + 10 if (mark + 10) in MARKS_TO_TEST else mark + 5
        tbl_now  = asks_at_mark(con, mark)
        tbl_prev = asks_at_mark(con, earlier_mark)

        row = con.execute(f"""
            WITH now_sig AS (
                SELECT market_id, resolution, up_ask, down_ask,
                    CASE
                        WHEN up_ask IS NULL OR down_ask IS NULL THEN NULL
                        WHEN up_ask >= {STABILITY_CONFIDENCE} AND up_ask > down_ask THEN 'UP'
                        WHEN down_ask >= {STABILITY_CONFIDENCE} AND down_ask > up_ask THEN 'DOWN'
                        ELSE NULL
                    END AS signal
                FROM {tbl_now}
            ),
            prev_sig AS (
                SELECT market_id,
                    CASE
                        WHEN up_ask IS NULL OR down_ask IS NULL THEN NULL
                        WHEN up_ask >= {STABILITY_CONFIDENCE} AND up_ask > down_ask THEN 'UP'
                        WHEN down_ask >= {STABILITY_CONFIDENCE} AND down_ask > up_ask THEN 'DOWN'
                        ELSE NULL
                    END AS signal
                FROM {tbl_prev}
            ),
            combined AS (
                SELECT
                    n.market_id, n.resolution, n.signal, n.up_ask, n.down_ask,
                    p.signal AS prev_signal,
                    CASE WHEN n.signal = 'UP' THEN n.up_ask ELSE n.down_ask END AS entry_price
                FROM now_sig n
                JOIN prev_sig p ON p.market_id = n.market_id
            ),
            final AS (
                SELECT *
                FROM combined
                WHERE signal IS NOT NULL
                  AND signal = prev_signal
                  AND entry_price <= {MAX_PRICE_CAP}
            )
            SELECT
                COUNT(*) AS n_signals,
                AVG(CASE
                        WHEN signal = 'UP'   AND resolution = 1 THEN 1.0
                        WHEN signal = 'DOWN' AND resolution = 0 THEN 1.0
                        ELSE 0.0
                    END) AS win_rate
            FROM final
        """).fetchone()

        n_signals, win_rate = row
        if not n_signals:
            print(f"T-{mark:>6}s  {n_signals or 0:>10}  {'--':>9}  no signals fired")
            continue
        note = "" if n_signals >= MIN_SAMPLE_SIZE else "small sample"
        beat = "  (beats baseline)" if win_rate > up_rate + 0.02 else ""
        print(f"T-{mark:>6}s  {n_signals:>10}  {win_rate:>8.1%}  {note}{beat}")


def main():
    con = duckdb.connect()
    n_markets = load_base_tables(con)
    if n_markets == 0:
        print("No markets loaded -- check dataset/columns still match this script.")
        return

    up_rate = con.execute("SELECT AVG(CAST(resolution AS DOUBLE)) FROM mkts").fetchone()[0]
    print(f"Baseline: UP wins {up_rate:.1%} of all 5-min BTC windows.\n")

    section1_confidence_only(con, up_rate)
    section2_stability_and_cap(con, up_rate)

    print("\nHow to read this:")
    print(" - 'beats baseline' is only flagged if win_rate is > baseline + 2 percentage points.")
    print("   Anything closer than that is noise, not edge.")
    print(f" - Trust win rates backed by n_signals >= {MIN_SAMPLE_SIZE} only.")
    print(" - Remember: even a real edge here doesn't yet account for Polymarket fees or")
    print("   the entry price itself (the $ profit per win vs $ loss per loss) -- a high win")
    print("   rate at a very expensive entry price can still be a losing strategy overall.")


if __name__ == "__main__":
    main()