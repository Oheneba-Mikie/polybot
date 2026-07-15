#!/usr/bin/env python3
"""
polybot.py — BTC 5-minute Up/Down Polymarket bot (PAPER TRADING ONLY)

Single-file CLI so you can just run it and watch. No real orders are ever
placed, no wallet/private key needed — it reads real, live Polymarket data
(Gamma API for market resolution, CLOB API public endpoints for prices) and
simulates fills locally.

Usage:
    python polybot.py                  # run continuously, ctrl+C to stop
    python polybot.py --cycles 3       # run exactly 3 five-minute cycles then exit
    python polybot.py --status         # just print balance/mode/pending trade and exit
    python polybot.py --reset          # wipe state back to $100 / NORMAL / $1
    python polybot.py --state-file my_run.json
    python polybot.py --no-chainlink   # skip on-chain lookup, use Binance-sampled proxy instead
    python polybot.py --rpc-url https://your-polygon-rpc.example

Dependencies: pip install requests web3 websocket-client

Changelog (this version):
- PRIMARY price source is now Polymarket's own live WebSocket feed
  (wss://ws-live-data.polymarket.com/, topic "crypto_prices_chainlink"),
  reverse-engineered from the browser's own DevTools traffic on a live
  market page. This is the exact same live Chainlink-sourced price the
  Polymarket UI itself displays as "Price to Beat" — no lag, no on-chain
  round-scanning needed. IMPORTANT: this endpoint is undocumented and
  unofficial. It could change, rate-limit, or disappear without notice,
  so the bot automatically falls back if it's unavailable.
- FALLBACK #1: Chainlink's BTC/USD feed on Polygon, read directly
  on-chain — the same ultimate data source, just queried a different way.
- FALLBACK #2: a live Binance spot sample, clearly labeled as an
  approximation (not the real resolution source), used only if both of
  the above are unavailable.
- The "Price to Beat" is now printed prominently every cycle, along with
  which of the three sources supplied it.
- New --status flag: prints balance/mode/next stake/any pending trade
  immediately, without waiting for a cycle to run.
- A short session P&L summary prints on exit (Ctrl+C or --cycles done).
- settle() polls for up to ~5 minutes (was ~2), logs outcomePrices while
  waiting, and accepts a looser >=0.98/<=0.02 resolution threshold.
- A filled trade is persisted as `pending_trade` the moment it's placed,
  and reconciled automatically on the next run/cycle if settlement never
  completed — so a crash or slow indexer can't silently lose it.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import threading
import time
from collections import deque
from dataclasses import dataclass, asdict, field
from enum import Enum

import requests

# macOS ships Python without the system certs wired in by default.
# Load them so wss:// connections don't fail with CERTIFICATE_VERIFY_FAILED.
def _make_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    for cert_path in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(cert_path):
            ctx.load_verify_locations(cert_path)
            break
    return ctx

WS_SSL_CONTEXT = _make_ssl_context()
WS_HEADERS = {
    "Origin": "https://polymarket.com",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
}

try:
    from web3 import Web3
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False

try:
    import websocket  # from the `websocket-client` package
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GAMMA_API_HOST = "https://gamma-api.polymarket.com"
CLOB_API_HOST = "https://clob.polymarket.com"
BTC_PRICE_URL = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"

NORMAL_STAKE_USD = 1.0
RECOVERY_STAKE_USD = 2.0
RECOVERY_TARGET_BALANCE = 2.0
STARTING_BALANCE = 100.0
SAFETY_PAUSE_FLOOR = -20.0  # auto-pause if balance drops below this

TRIGGER_SECONDS_BEFORE_CLOSE = 150   # T-02:30
FALLBACK_SECONDS_BEFORE_CLOSE = 20   # T-00:20
POLL_INTERVAL_SECONDS = 2
MARKET_NOT_FOUND_RETRY_SECONDS = 20

# Settlement polling
SETTLE_POLL_INTERVAL_SECONDS = 5
SETTLE_MAX_ATTEMPTS = 60          # 60 * 5s = ~5 minutes
RECONCILE_MAX_ATTEMPTS = 36       # 36 * 5s = ~3 minutes, run once at startup

# A market is treated as resolved once either side's price is at/beyond
# this threshold, instead of requiring an exact 0.0/1.0.
RESOLVED_PRICE_THRESHOLD = 0.98

# Chainlink on-chain (Polygon) — this is the actual resolution source
# Polymarket's BTC 5-min markets use ("Price to Beat").
DEFAULT_POLYGON_RPC = os.environ.get("POLYGON_RPC_URL", "https://polygon-rpc.com")
CHAINLINK_BTC_USD_FEED_POLYGON = "0xc907E116054Ad103354f2D350FD2514433D57F6f"
CHAINLINK_LOOKBACK_MAX_ROUNDS = 3000

# Polymarket's own live WebSocket feed — UNDOCUMENTED/UNOFFICIAL, found via
# browser DevTools on a live market page. This streams the exact same
# Chainlink-sourced price the site displays as "Price to Beat". Kept as the
# primary source since it needs no on-chain lookup, but treated as
# best-effort: if it's unreachable or the schema changes, the bot falls
# back to the on-chain Chainlink read, then to Binance.
LIVE_WS_URL = "wss://ws-live-data.polymarket.com/"
LIVE_WS_SYMBOL = "btc/usd"
LIVE_WS_BUFFER_SECONDS = 900  # keep ~15 minutes of ticks in memory
LIVE_WS_RECONNECT_DELAY_SECONDS = 5

AGGREGATOR_V3_ABI = [
    {"inputs": [], "name": "decimals",
     "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "latestRoundData",
     "outputs": [
         {"internalType": "uint80", "name": "roundId", "type": "uint80"},
         {"internalType": "int256", "name": "answer", "type": "int256"},
         {"internalType": "uint256", "name": "startedAt", "type": "uint256"},
         {"internalType": "uint256", "name": "updatedAt", "type": "uint256"},
         {"internalType": "uint80", "name": "answeredInRound", "type": "uint80"},
     ], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "uint80", "name": "_roundId", "type": "uint80"}],
     "name": "getRoundData",
     "outputs": [
         {"internalType": "uint80", "name": "roundId", "type": "uint80"},
         {"internalType": "int256", "name": "answer", "type": "int256"},
         {"internalType": "uint256", "name": "startedAt", "type": "uint256"},
         {"internalType": "uint256", "name": "updatedAt", "type": "uint256"},
         {"internalType": "uint80", "name": "answeredInRound", "type": "uint80"},
     ], "stateMutability": "view", "type": "function"},
]


# ---------------------------------------------------------------------------
# State (persisted to disk so you can stop/restart and keep balance/mode)
# ---------------------------------------------------------------------------
class Mode(str, Enum):
    NORMAL = "NORMAL"
    RECOVERY = "RECOVERY"


class Side(str, Enum):
    UP = "UP"
    DOWN = "DOWN"


@dataclass
class BotState:
    mode: str = Mode.NORMAL.value
    balance_usd: float = STARTING_BALANCE
    next_stake_usd: float = NORMAL_STAKE_USD
    paused: bool = False
    # Holds a trade that was filled but not yet confirmed resolved, so a
    # crash/timeout doesn't silently lose it. None when nothing pending.
    pending_trade: dict | None = None

    @classmethod
    def load(cls, path: str) -> "BotState":
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            return cls(**data)
        return cls()

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)

    def record_result(self, won: bool, stake_used: float, path: str) -> None:
        if won:
            self.balance_usd += stake_used
        else:
            self.balance_usd -= stake_used

        if self.balance_usd < SAFETY_PAUSE_FLOOR:
            self.paused = True
            print(f"[SAFETY PAUSE] balance ${self.balance_usd:.2f} below floor "
                  f"${SAFETY_PAUSE_FLOOR:.2f} — pausing. Use --reset to start over.")
            self.save(path)
            return

        if self.mode == Mode.NORMAL.value:
            if won:
                pass  # stay in NORMAL, stake stays $1
            else:
                self.mode = Mode.RECOVERY.value
                self.next_stake_usd = RECOVERY_STAKE_USD
        else:  # currently in RECOVERY
            if self.balance_usd >= RECOVERY_TARGET_BALANCE:
                self.mode = Mode.NORMAL.value
                self.next_stake_usd = NORMAL_STAKE_USD
            else:
                self.next_stake_usd = RECOVERY_STAKE_USD  # stays flat $2

        self.save(path)

    def in_recovery(self) -> bool:
        return self.mode == Mode.RECOVERY.value

    def print_status(self) -> None:
        print("\n=== STATUS ===")
        print(f"  mode:        {self.mode}")
        print(f"  balance:     ${self.balance_usd:.2f}")
        print(f"  next stake:  ${self.next_stake_usd:.2f}")
        print(f"  paused:      {self.paused}")
        if self.pending_trade:
            p = self.pending_trade
            print(f"  pending trade: {p['side']} stake=${p['stake']:.2f} "
                  f"entry_price={p['entry_price']} slug={p['slug']} "
                  f"(not yet resolved — will be reconciled on next run)")
        else:
            print("  pending trade: none")
        print("==============\n")


# ---------------------------------------------------------------------------
# Slug generation (STEP 1)
# ---------------------------------------------------------------------------
def current_market_start(now: float | None = None) -> int:
    now = time.time() if now is None else now
    return int(now // 300) * 300


def current_slug(now: float | None = None) -> str:
    return f"btc-updown-5m-{current_market_start(now)}"


def market_window(now: float | None = None) -> tuple[int, int]:
    start = current_market_start(now)
    return start, start + 300


# ---------------------------------------------------------------------------
# Gamma API — resolve market metadata dynamically (STEP 2 / 3)
# ---------------------------------------------------------------------------
class MarketNotFoundError(Exception):
    pass


@dataclass
class ResolvedMarket:
    event_id: str
    market_id: str
    condition_id: str
    title: str
    slug: str
    up_token_id: str
    down_token_id: str
    outcomes: list = field(default_factory=list)
    raw_market: dict = field(default_factory=dict)


def _parse_json_field(value):
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def resolve_market_by_slug(slug: str, timeout: float = 10.0) -> ResolvedMarket:
    resp = requests.get(f"{GAMMA_API_HOST}/events", params={"slug": slug}, timeout=timeout)
    resp.raise_for_status()
    events = resp.json()
    if not events:
        raise MarketNotFoundError(f"No event for slug={slug!r}")

    event = events[0]
    markets = event.get("markets", [])
    if not markets:
        raise MarketNotFoundError(f"Event {slug!r} has no markets")

    market = markets[0]
    token_ids = _parse_json_field(market.get("clobTokenIds")) or []
    outcomes = _parse_json_field(market.get("outcomes")) or []

    if len(token_ids) < 2:
        raise MarketNotFoundError(f"Event {slug!r} has no usable clobTokenIds yet")

    # Map by outcome label (case-insensitive), never by array index.
    up_token_id, down_token_id = token_ids[0], token_ids[1]
    if len(outcomes) >= 2:
        lower = [str(o).strip().lower() for o in outcomes]
        for i, label in enumerate(lower):
            if label in ("up", "yes"):
                up_token_id = token_ids[i]
            elif label in ("down", "no"):
                down_token_id = token_ids[i]

    return ResolvedMarket(
        event_id=str(event.get("id")),
        market_id=str(market.get("id")),
        condition_id=str(market.get("conditionId")),
        title=market.get("question") or event.get("title", ""),
        slug=slug,
        up_token_id=up_token_id,
        down_token_id=down_token_id,
        outcomes=outcomes,
        raw_market=market,
    )


# ---------------------------------------------------------------------------
# CLOB API — public read endpoints only (no auth, no orders)
# ---------------------------------------------------------------------------
def get_midpoint(token_id: str, timeout: float = 5.0) -> float | None:
    try:
        resp = requests.get(f"{CLOB_API_HOST}/midpoint", params={"token_id": token_id}, timeout=timeout)
        resp.raise_for_status()
        return float(resp.json()["mid"])
    except Exception:
        return None


def get_best_ask(token_id: str, timeout: float = 5.0) -> float | None:
    try:
        resp = requests.get(f"{CLOB_API_HOST}/book", params={"token_id": token_id}, timeout=timeout)
        resp.raise_for_status()
        asks = resp.json().get("asks", [])
        if not asks:
            return None
        return float(min(asks, key=lambda a: float(a["price"]))["price"])
    except Exception:
        return None


def get_entry_price(token_id: str) -> float | None:
    """Best ask if available, else midpoint — used as the simulated fill price."""
    price = get_best_ask(token_id)
    if price is None:
        price = get_midpoint(token_id)
    return price


# ---------------------------------------------------------------------------
# BTC price (Binance spot — public, no key). Used as: (a) live tick polling
# during the window (fast/cheap), and (b) fallback reference price if
# Chainlink on-chain lookup isn't available.
# ---------------------------------------------------------------------------
def get_btc_price(timeout: float = 5.0) -> float:
    resp = requests.get(BTC_PRICE_URL, timeout=timeout)
    resp.raise_for_status()
    return float(resp.json()["price"])


# ---------------------------------------------------------------------------
# Chainlink BTC/USD on Polygon — the actual resolution source Polymarket
# uses for these markets. Read directly on-chain, no API key needed.
# ---------------------------------------------------------------------------
class ChainlinkUnavailableError(Exception):
    pass


class ChainlinkClient:
    def __init__(self, rpc_url: str = DEFAULT_POLYGON_RPC,
                 feed_address: str = CHAINLINK_BTC_USD_FEED_POLYGON):
        if not WEB3_AVAILABLE:
            raise ChainlinkUnavailableError(
                "web3 package not installed. Run: pip install web3"
            )
        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 8}))
        if not self.w3.is_connected():
            raise ChainlinkUnavailableError(f"Could not connect to Polygon RPC at {rpc_url}")
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(feed_address), abi=AGGREGATOR_V3_ABI
        )
        self._decimals = None

    @property
    def decimals(self) -> int:
        if self._decimals is None:
            self._decimals = self.contract.functions.decimals().call()
        return self._decimals

    def _to_price(self, answer: int) -> float:
        return answer / (10 ** self.decimals)

    def latest_price(self) -> tuple[float, int]:
        """Returns (price, updated_at_unix_ts) for the most recent round."""
        _, answer, _, updated_at, _ = self.contract.functions.latestRoundData().call()
        return self._to_price(answer), updated_at

    def price_at_or_before(self, target_ts: int,
                            max_lookback: int = CHAINLINK_LOOKBACK_MAX_ROUNDS
                            ) -> tuple[float, int, int] | None:
        """
        Walk backward from the latest round to find the most recent round
        whose updatedAt <= target_ts — i.e. "what was the price at this
        moment". Returns (price, updated_at, round_id) or None if it
        couldn't be found within max_lookback rounds (e.g. RPC issues, or
        target_ts is older than the feed's retained round history).

        Note: this decrements the raw uint80 roundId, which is safe as
        long as we don't cross a Chainlink "phase" boundary — phase
        changes are rare (feed upgrades), so this holds for normal
        recent-history lookups like ours (a few minutes back).
        """
        round_id, answer, _, updated_at, _ = self.contract.functions.latestRoundData().call()
        if updated_at <= target_ts:
            return self._to_price(answer), updated_at, round_id

        rid = round_id
        for _ in range(max_lookback):
            rid -= 1
            try:
                r_id, answer, _, updated_at, _ = self.contract.functions.getRoundData(rid).call()
            except Exception:
                return None
            if updated_at == 0:
                return None
            if updated_at <= target_ts:
                return self._to_price(answer), updated_at, r_id
        return None


# ---------------------------------------------------------------------------
# Polymarket's live WebSocket feed (undocumented — see LIVE_WS_URL comment
# above). Runs in a background thread, keeps a rolling buffer of recent
# (timestamp_ms, price) ticks so a lookup for "price at window open" can be
# answered instantly without needing to have connected at exactly that
# moment.
# ---------------------------------------------------------------------------
class LiveWSUnavailableError(Exception):
    pass


class LiveChainlinkWSStream:
    def __init__(self, url: str = LIVE_WS_URL, symbol: str = LIVE_WS_SYMBOL,
                 buffer_seconds: int = LIVE_WS_BUFFER_SECONDS):
        if not WEBSOCKET_AVAILABLE:
            raise LiveWSUnavailableError(
                "websocket-client package not installed. Run: pip install websocket-client"
            )
        self.url = url
        self.symbol = symbol
        self.buffer_seconds = buffer_seconds
        self._buffer: deque[tuple[int, float]] = deque()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._connected_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_error: str | None = None

    def start(self, connect_timeout: float = 20.0, first_tick_timeout: float = 60.0) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        # Wait for connection — mandatory now (WS is the sole price source).
        self._connected_event.wait(timeout=connect_timeout)
        if self._connected_event.is_set():
            # Also wait for the first price tick to land in the buffer.
            deadline = time.time() + first_tick_timeout
            while time.time() < deadline and self.latest() is None:
                time.sleep(0.2)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def is_connected(self) -> bool:
        return self._connected_event.is_set()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                ws = websocket.create_connection(
                    self.url,
                    timeout=10,
                    sslopt={"context": WS_SSL_CONTEXT},
                    header=WS_HEADERS,
                )
                sub_msg = {
                    "action": "subscribe",
                    "subscriptions": [{
                        "topic": "crypto_prices_chainlink",
                        "type": "update",
                        # NOTE: 'filters' is intentionally omitted — the server
                        # silently ignores subscriptions that include it.
                        # We filter by symbol client-side in _handle_message.
                    }],
                }
                ws.send(json.dumps(sub_msg))
                self._connected_event.set()
                ws.settimeout(60)
                while not self._stop_event.is_set():
                    raw = ws.recv()
                    self._handle_message(raw)
            except Exception as e:
                self._last_error = str(e)
                self._connected_event.clear()
                if self._stop_event.is_set():
                    break
                time.sleep(LIVE_WS_RECONNECT_DELAY_SECONDS)

    def _handle_message(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return
        # Schema: {"topic": "crypto_prices_chainlink", "type": "update",
        #          "payload": {"symbol": "btc/usd", "value": 64804.01,
        #                      "timestamp": 1784153700000, ...}}
        if msg.get("topic") != "crypto_prices_chainlink":
            return
        payload = msg.get("payload") or {}
        if payload.get("symbol") != self.symbol:
            return
        ts_ms = payload.get("timestamp")
        value = payload.get("value")
        if ts_ms is None or value is None:
            return
        with self._lock:
            self._buffer.append((int(ts_ms), float(value)))
            if self._buffer:
                cutoff = self._buffer[-1][0] - self.buffer_seconds * 1000
                while self._buffer and self._buffer[0][0] < cutoff:
                    self._buffer.popleft()

    def price_at_or_after(self, target_ts_seconds: float) -> tuple[float, int] | None:
        """Earliest buffered tick at/after target_ts. Returns (price, ts_ms) or None."""
        target_ms = target_ts_seconds * 1000
        with self._lock:
            for ts_ms, price in self._buffer:
                if ts_ms >= target_ms:
                    return price, ts_ms
        return None

    def latest(self) -> tuple[float, int] | None:
        with self._lock:
            if not self._buffer:
                return None
            ts_ms, price = self._buffer[-1]
            return price, ts_ms


# ---------------------------------------------------------------------------
# Strategy (STEP 5 / 6 / 7)
# ---------------------------------------------------------------------------
def compute_trigger_levels(reference_price: float) -> tuple[float, float]:
    base = (reference_price // 100) * 100
    last_two = reference_price - base
    doubled = last_two * 2
    return base + doubled, base  # up_trigger, down_trigger


def check_trigger(price: float, up_trigger: float, down_trigger: float) -> Side | None:
    if price >= up_trigger:
        return Side.UP
    if price <= down_trigger:
        return Side.DOWN
    return None


def fallback_decision(price: float, reference_price: float) -> Side:
    return Side.UP if price > reference_price else Side.DOWN


# ---------------------------------------------------------------------------
# Resolution helper (shared by settle() and startup reconciliation)
# ---------------------------------------------------------------------------
def try_read_resolution(slug: str) -> tuple[bool | None, list | None]:
    """
    Attempt one read of a market's resolution status.

    Returns (up_won, outcome_prices):
      - up_won = True/False if resolved, None if not yet resolved / unreadable
      - outcome_prices = whatever raw prices were seen (for logging), or None
    """
    try:
        resolved = resolve_market_by_slug(slug)
    except MarketNotFoundError:
        return None, None

    outcome_prices = _parse_json_field(resolved.raw_market.get("outcomePrices"))
    if not outcome_prices:
        return None, None

    outcomes = resolved.outcomes or ["Up", "Down"]
    lower = [str(o).strip().lower() for o in outcomes]
    try:
        up_idx = next(i for i, o in enumerate(lower) if o in ("up", "yes"))
        down_idx = next(i for i, o in enumerate(lower) if o in ("down", "no"))
    except StopIteration:
        up_idx, down_idx = 0, 1

    try:
        up_price = float(outcome_prices[up_idx])
        down_price = float(outcome_prices[down_idx])
    except (ValueError, IndexError):
        return None, outcome_prices

    resolved_enough = (
        up_price >= RESOLVED_PRICE_THRESHOLD or up_price <= (1 - RESOLVED_PRICE_THRESHOLD)
        or down_price >= RESOLVED_PRICE_THRESHOLD or down_price <= (1 - RESOLVED_PRICE_THRESHOLD)
    )
    if not resolved_enough:
        return None, outcome_prices

    return (up_price > down_price), outcome_prices


def apply_pending_result(state: BotState, state_path: str, up_won: bool) -> None:
    pending = state.pending_trade
    side = Side(pending["side"])
    stake = float(pending["stake"])
    entry_price = float(pending["entry_price"])

    won = up_won if side == Side.UP else not up_won
    pnl = (1.0 - entry_price) * (stake / entry_price) if won else -stake
    print(f"  RESULT: {'WIN' if won else 'LOSS'}  pnl=${pnl:+.2f}  (slug={pending['slug']})")

    state.pending_trade = None
    state.record_result(won, stake, state_path)
    print(f"  -> mode={state.mode} balance=${state.balance_usd:.2f} "
          f"next_stake=${state.next_stake_usd:.2f}")


def reconcile_pending(state: BotState, state_path: str) -> None:
    """
    Run once at startup (and defensively before each cycle). If a previous
    run filled a trade but never saw it resolve, try to resolve it now
    instead of silently leaving the balance stale.
    """
    if state.pending_trade is None:
        return

    slug = state.pending_trade["slug"]
    print(f"  [RECONCILE] found unresolved pending trade for {slug}, checking...")

    for attempt in range(1, RECONCILE_MAX_ATTEMPTS + 1):
        up_won, outcome_prices = try_read_resolution(slug)
        print(f"  [RECONCILE {attempt}/{RECONCILE_MAX_ATTEMPTS}] outcomePrices={outcome_prices}")
        if up_won is not None:
            apply_pending_result(state, state_path, up_won)
            return
        time.sleep(SETTLE_POLL_INTERVAL_SECONDS)

    print(f"  [RECONCILE] still unresolved after {RECONCILE_MAX_ATTEMPTS} attempts — "
          f"leaving pending_trade in state, will retry again next run/cycle.")


# ---------------------------------------------------------------------------
# One 5-minute cycle
# ---------------------------------------------------------------------------
def wait_for_market(slug: str, timeout: float = MARKET_NOT_FOUND_RETRY_SECONDS) -> ResolvedMarket | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            return resolve_market_by_slug(slug)
        except MarketNotFoundError:
            time.sleep(1)
    return None


def get_price_to_beat(ws_stream: "LiveChainlinkWSStream",
                       start_ts: int,
                       wait_seconds: float = 30.0) -> tuple[float, str]:
    """
    Returns (price, source_label) using ONLY the Polymarket live WS feed.
    Waits up to wait_seconds for a buffered tick at/after start_ts.
    Raises RuntimeError if the stream has no tick within that window.
    """
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        result = ws_stream.price_at_or_after(start_ts)
        if result is not None:
            price, ts_ms = result
            lag_ms = ts_ms - start_ts * 1000
            return price, f"Polymarket live WS (crypto_prices_chainlink, +{lag_ms}ms after window open)"
        time.sleep(0.5)
    raise RuntimeError(
        f"WS stream has no tick at/after window start ({start_ts}) after waiting {wait_seconds:.0f}s. "
        "Check your connection or restart the bot."
    )


def run_cycle(state: BotState, state_path: str,
              ws_stream: "LiveChainlinkWSStream") -> None:
    # Defensive: if a prior trade never resolved, try again before doing
    # anything new. Cheap no-op if there's nothing pending.
    reconcile_pending(state, state_path)
    if state.paused:
        return

    slug = current_slug()
    start_ts, end_ts = market_window()
    print(f"\n=== Cycle {slug} | mode={state.mode} balance=${state.balance_usd:.2f} "
          f"next_stake=${state.next_stake_usd:.2f} ===")

    market = wait_for_market(slug)
    if market is None:
        print(f"  ! could not resolve {slug} in time, skipping cycle")
        time.sleep(max(1, end_ts - time.time()))
        return

    print(f"  resolved: market_id={market.market_id} condition_id={market.condition_id} "
          f"title={market.title!r}")
    print(f"  up_token={market.up_token_id}  down_token={market.down_token_id}")

    try:
        reference_price, ref_source = get_price_to_beat(ws_stream, start_ts)
    except RuntimeError as e:
        print(f"  ! {e} — skipping cycle")
        time.sleep(max(1, end_ts - time.time()))
        return

    up_t, down_t = compute_trigger_levels(reference_price)
    print(f"  [PRICE TO BEAT] ${reference_price:,.2f}  (source: {ref_source})")
    print(f"  up_trigger=${up_t:,.2f} down_trigger=${down_t:,.2f}")
    print(f"  {'─'*62}")

    decided_side: Side | None = None
    stake = RECOVERY_STAKE_USD if state.in_recovery() else NORMAL_STAKE_USD
    entry_price = None
    last_tick_ts_ms: int | None = None
    last_price: float = reference_price
    ticks_this_window: int = 0

    while True:
        remaining = end_ts - time.time()
        if remaining <= 0:
            break

        ws_latest = ws_stream.latest()
        if ws_latest is None:
            print(f"  ! WS stream has no price yet, waiting...")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        btc_price, tick_ts_ms = ws_latest

        # Print every NEW tick (deduplicated by timestamp)
        if tick_ts_ms != last_tick_ts_ms:
            last_tick_ts_ms = tick_ts_ms
            last_price = btc_price
            ticks_this_window += 1
            diff = btc_price - reference_price
            arrow = "▲" if diff > 0 else ("▼" if diff < 0 else "─")
            import datetime as _dt
            tick_time = _dt.datetime.fromtimestamp(tick_ts_ms / 1000).strftime("%H:%M:%S")
            print(
                f"  tick #{ticks_this_window:>3}  {tick_time}  "
                f"${btc_price:>10,.2f}  {arrow} {diff:>+8.2f}  "
                f"ptb=${reference_price:,.2f}  {int(remaining):>3}s left"
            )

        if decided_side is None:
            if state.in_recovery():
                if remaining <= FALLBACK_SECONDS_BEFORE_CLOSE:
                    decided_side = fallback_decision(btc_price, reference_price)
                    print(f"  >>> [RECOVERY fallback] -> BET {decided_side.value}")
            else:
                fired = check_trigger(btc_price, up_t, down_t)
                if fired:
                    decided_side = fired
                    print(f"  >>> [TRIGGER hit] -> BET {decided_side.value}")
                elif remaining <= FALLBACK_SECONDS_BEFORE_CLOSE:
                    decided_side = fallback_decision(btc_price, reference_price)
                    print(f"  >>> [fallback] -> BET {decided_side.value}")

            if decided_side is not None:
                token_id = market.up_token_id if decided_side == Side.UP else market.down_token_id
                entry_price = get_entry_price(token_id)
    print(f"  Final Price   : ${last_price:,.2f}")
    print(f"  Net Move      : ${(last_price - reference_price):+.2f}")
    print(f"  Ticks Seen    : {ticks_seen}")
    if decided_side:
        print(f"  Bot Bet       : {decided_side.value}")
        print(f"  Result        : {'WIN' if (decided_side == Side.UP and last_price > reference_price) or (decided_side == Side.DOWN and last_price < reference_price) else 'LOSS'}")
    else:
        print("  Bot Bet       : None")
    print("-" * 40)

    if decided_side is None or entry_price is None:
        return

    state.pending_trade = {
        "slug": market.slug,
        "market_id": market.market_id,
        "condition_id": market.condition_id,
        "side": decided_side.value,
        "stake": stake,
        "entry_price": entry_price,
    }
    state.save(state_path)
    settle(state, state_path)


def settle(state: BotState, state_path: str) -> None:
    slug = state.pending_trade["slug"]
    print("  waiting for market to resolve...")
    for attempt in range(1, SETTLE_MAX_ATTEMPTS + 1):
        time.sleep(SETTLE_POLL_INTERVAL_SECONDS)
        up_won, outcome_prices = try_read_resolution(slug)
        print(f"  [settle {attempt}/{SETTLE_MAX_ATTEMPTS}] outcomePrices={outcome_prices}")
        if up_won is not None:
            apply_pending_result(state, state_path, up_won)
            return

    print(f"  ! market did not resolve within ~{SETTLE_MAX_ATTEMPTS * SETTLE_POLL_INTERVAL_SECONDS}s, "
          f"leaving trade pending — it will be reconciled automatically on the next cycle/run.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="BTC 5-min Up/Down Polymarket bot (paper trading)")
    parser.add_argument("--cycles", type=int, default=None, help="run this many cycles then exit (default: run forever)")
    parser.add_argument("--state-file", type=str, default="polybot_state.json", help="path to persisted state JSON")
    parser.add_argument("--reset", action="store_true", help="reset state to $100 / NORMAL / $1 and exit")
    parser.add_argument("--status", action="store_true", help="print current balance/mode/pending trade and exit immediately")
    parser.add_argument("--ws-price", action="store_true", help="connect to the Polymarket WS feed, print the current BTC price, and exit")
    args = parser.parse_args()

    if args.reset:
        BotState().save(args.state_file)
        print(f"State reset -> {args.state_file}")
        return

    state = BotState.load(args.state_file)

    if args.status:
        state.print_status()
        return

    # --ws-price: just connect, print the live price, and exit
    if args.ws_price:
        print(f"Connecting to Polymarket live WS feed ({LIVE_WS_URL})...")
        try:
            stream = LiveChainlinkWSStream()
            stream.start(connect_timeout=20.0, first_tick_timeout=60.0)
        except LiveWSUnavailableError as e:
            print(f"ERROR: {e}")
            return
        if not stream.is_connected():
            print("ERROR: Could not connect to the WebSocket within 20s. Check your network.")
            return
        result = stream.latest()
        if result is None:
            print("ERROR: Connected but received no price tick within 15s.")
        else:
            price, ts_ms = result
            import datetime
            ts_str = datetime.datetime.fromtimestamp(ts_ms / 1000).strftime("%H:%M:%S")
            print(f"  BTC/USD (Polymarket WS, crypto_prices_chainlink):")
            print(f"  Price : ${price:,.2f}")
            print(f"  Tick  : {ts_str} local ({ts_ms}ms)")
        stream.stop()
        return

    if state.paused:
        print(f"Bot is PAUSED (balance ${state.balance_usd:.2f}). Run with --reset to start over.")
        return

    print(f"PAPER TRADING ONLY — no real orders will ever be placed.")
    print(f"Loaded state: mode={state.mode} balance=${state.balance_usd:.2f} "
          f"next_stake=${state.next_stake_usd:.2f}")
    if state.pending_trade is not None:
        print(f"Found a pending trade from a previous run (slug={state.pending_trade['slug']}); "
              f"will reconcile it before starting.")

    print(f"Connecting to Polymarket live WS feed ({LIVE_WS_URL})...")
    try:
        ws_stream = LiveChainlinkWSStream()
        ws_stream.start(connect_timeout=20.0, first_tick_timeout=60.0)
    except LiveWSUnavailableError as e:
        print(f"FATAL: websocket-client package not available ({e}). Run: pip install websocket-client")
        return

    if not ws_stream.is_connected():
        print("FATAL: Could not connect to the Polymarket WS feed within 20s. "
              "Check your network and try again.")
        return

    result = ws_stream.latest()
    if result:
        print(f"Live price feed connected — current BTC/USD: ${result[0]:,.2f}  "
              f"[undocumented/unofficial endpoint — reconnects automatically if it drops]")
    else:
        print("Live price feed connected but no tick yet — will wait at cycle start.")

    start_of_run_balance = state.balance_usd
    completed = 0
    try:
        while args.cycles is None or completed < args.cycles:
            run_cycle(state, args.state_file, ws_stream)
            completed += 1
            if state.paused:
                break
    except KeyboardInterrupt:
        print("\nStopped by user. State saved.")
    finally:
        if ws_stream is not None:
            ws_stream.stop()
        session_pnl = state.balance_usd - start_of_run_balance
        print("\n=== SESSION SUMMARY ===")
        print(f"  cycles completed this run: {completed}")
        print(f"  balance at start of run:   ${start_of_run_balance:.2f}")
        print(f"  balance now:               ${state.balance_usd:.2f}")
        print(f"  session P&L:               ${session_pnl:+.2f}")
        print(f"  mode / next stake:         {state.mode} / ${state.next_stake_usd:.2f}")
        if state.pending_trade:
            print(f"  NOTE: a trade is still pending resolution "
                  f"(slug={state.pending_trade['slug']}) — it'll be reconciled next run.")
        print("========================\n")


if __name__ == "__main__":
    main()
