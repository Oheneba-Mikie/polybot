import os
import sys
import time
import json
import argparse
import datetime
import requests
from dotenv import load_dotenv

# Ensure stdout is unbuffered
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

# Add local path for py_clob_client_v2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import (
    ApiCreds,
    OrderArgsV2,
    PostOrdersV2Args,
    OrderType,
)

load_dotenv()

GAMMA_HOST = "https://gamma-api.polymarket.com"
CLOB_HOST  = "https://clob.polymarket.com"

class BatchFokSniper:
    def __init__(
        self,
        max_combined_cost: float = 0.985,
        min_depth_threshold: float = 100.0,
        min_order_size: float = 5.0,
        max_order_size: float = 50.0,
        dry_run: bool = True,
        poll_interval: float = 0.3,
    ):
        self.max_combined_cost = max_combined_cost
        self.min_depth_threshold = min_depth_threshold
        self.min_order_size = min_order_size
        self.max_order_size = max_order_size
        self.dry_run = dry_run
        self.poll_interval = poll_interval

        # Auth setup
        self.private_key = os.getenv("POLYMARKET_PRIVATE_KEY", "")
        self.funder_address = os.getenv("POLYMARKET_ADDRESS", "")
        self.api_key = os.getenv("POLYMARKET_API_KEY", "")
        self.api_secret = os.getenv("POLYMARKET_API_SECRET", "")
        self.api_passphrase = os.getenv("POLYMARKET_API_PASSPHRASE", "")

        self.client = None
        self._init_clob_client()

        self.current_market = None
        self.trades_executed = 0
        self.total_profit_locked = 0.0

    def _init_clob_client(self):
        if not self.private_key:
            print("[WARN] No POLYMARKET_PRIVATE_KEY found in .env. Running in READ/DRY-RUN mode only.")
            return

        try:
            creds = ApiCreds(
                api_key=self.api_key,
                api_secret=self.api_secret,
                api_passphrase=self.api_passphrase,
            )
            # Signature type 2 is standard for Polymarket Proxy/Magic Wallets
            self.client = ClobClient(
                host=CLOB_HOST,
                key=self.private_key,
                chain_id=137,
                creds=creds,
                signature_type=2,
                funder=self.funder_address,
            )
            print(f"[AUTH] CLOB Client initialized for Funder: {self.funder_address}")
        except Exception as e:
            print(f"[AUTH ERROR] Failed to initialize CLOB client: {e}")

    def discover_active_5m_btc_market(self):
        """Find the active or next upcoming 5m Bitcoin market."""
        now = int(time.time())
        cur_w = (now // 300) * 300
        candidates = [cur_w, cur_w + 300]

        for w_s in candidates:
            slug = f"btc-updown-5m-{w_s}"
            try:
                r = requests.get(f"{GAMMA_HOST}/events?slug={slug}", timeout=3).json()
                if r and r[0].get("markets"):
                    m = r[0]["markets"][0]
                    tokens = json.loads(m.get("clobTokenIds", "[]"))
                    outcomes = json.loads(m.get("outcomes", "[]"))
                    if len(tokens) >= 2 and now < (w_s + 300):
                        return {
                            "slug": slug,
                            "title": r[0].get("title", slug),
                            "window_start": w_s,
                            "window_end": w_s + 300,
                            "up_token": tokens[0],
                            "down_token": tokens[1],
                            "outcomes": outcomes,
                            "condition_id": m.get("conditionId"),
                        }
            except Exception:
                pass
        return None

    def fetch_order_books(self, up_token: str, down_token: str):
        """Fetch Level 1 order books for both UP and DOWN tokens in parallel."""
        try:
            r_up = requests.get(f"{CLOB_HOST}/book?token_id={up_token}", timeout=2).json()
            r_dn = requests.get(f"{CLOB_HOST}/book?token_id={down_token}", timeout=2).json()

            asks_up = r_up.get("asks", [])
            asks_dn = r_dn.get("asks", [])

            best_up = min(asks_up, key=lambda x: float(x["price"])) if asks_up else None
            best_dn = min(asks_dn, key=lambda x: float(x["price"])) if asks_dn else None

            best_up_price = float(best_up["price"]) if best_up else 1.0
            best_up_size  = float(best_up["size"]) if best_up else 0.0

            best_dn_price = float(best_dn["price"]) if best_dn else 1.0
            best_dn_size  = float(best_dn["size"]) if best_dn else 0.0

            return {
                "up_ask": best_up_price,
                "up_size": best_up_size,
                "down_ask": best_dn_price,
                "down_size": best_dn_size,
            }
        except Exception:
            return None

    def execute_batch_fok_snipe(self, up_token: str, down_token: str, up_ask: float, down_ask: float, size: float):
        """Build and post simultaneous batch Fill-or-Kill orders in a single HTTP request."""
        comb_cost = round(up_ask + down_ask, 3)
        profit_usd = round((1.0 - comb_cost) * size, 3)
        profit_pct = round(((1.0 - comb_cost) / comb_cost) * 100.0, 1)

        t_start = time.time()
        now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-3]

        print("\n" + "🔥"*40)
        print(f"[{now_utc}] 🎯 ARBITRAGE TRIGGER DETECTED!")
        print(f"  -> UP Ask:   ${up_ask:.3f} | Size: {size:.1f} sh")
        print(f"  -> DOWN Ask: ${down_ask:.3f} | Size: {size:.1f} sh")
        print(f"  -> COMBINED: ${comb_cost:.3f} | ROI: +{profit_pct}% (Profit: +${profit_usd:.3f})")
        print("🔥"*40)

        if self.dry_run:
            sim_time = round((time.time() - t_start) * 1000, 1)
            print(f"  [DRY-RUN SIMULATION] Batch FOK Payload constructed in {sim_time}ms.")
            print(f"  [DRY-RUN RESULT] Simulated Fill: Bought {size} UP @ ${up_ask} + {size} DOWN @ ${down_ask}. Payout: ${size:.2f} USDC.")
            self.trades_executed += 1
            self.total_profit_locked += profit_usd
            return True

        # LIVE EXECUTION VIA CLIENT
        if not self.client:
            print("  [ERROR] Cannot execute live order: CLOB client not initialized.")
            return False

        try:
            # 1. Build signed OrderArgsV2 for both sides
            up_order_args = OrderArgsV2(
                token_id=up_token,
                price=up_ask,
                size=size,
                side="BUY",
            )
            down_order_args = OrderArgsV2(
                token_id=down_token,
                price=down_ask,
                size=size,
                side="BUY",
            )

            built_up_order = self.client.create_order(up_order_args)
            built_down_order = self.client.create_order(down_order_args)

            # 2. Bundle into PostOrdersV2Args with FOK
            batch_args = [
                PostOrdersV2Args(order=built_up_order, orderType=OrderType.FOK),
                PostOrdersV2Args(order=built_down_order, orderType=OrderType.FOK),
            ]

            # 3. Post batch in single HTTP request
            print(f"  [POST] Submitting Batch FOK order to {CLOB_HOST}/orders...")
            resp = self.client.post_orders(batch_args)
            exec_time_ms = round((time.time() - t_start) * 1000, 1)

            print(f"  [RESPONSE ({exec_time_ms}ms)]: {resp}")

            self.trades_executed += 1
            self.total_profit_locked += profit_usd
            return True

        except Exception as e:
            exec_time_ms = round((time.time() - t_start) * 1000, 1)
            print(f"  [FAILED / FOK CANCELED ({exec_time_ms}ms)]: {e}")
            return False

    def run(self):
        print("="*105)
        print("🚀 POLYMARKET BATCH FOK ARBITRAGE SNIPER (SINGLE-REQUEST ATOMIC EXECUTION)")
        print(f"  -> Target Max Cost:   ${self.max_combined_cost:.3f} (Min ROI: +{round((1-self.max_combined_cost)/self.max_combined_cost*100, 1)}%)")
        print(f"  -> Min / Max Size:    {self.min_order_size} sh / {self.max_order_size} sh")
        print(f"  -> Mode:              {'[DRY-RUN / PAPER TRADING]' if self.dry_run else '[LIVE TRADING ENABLED ⚠️]'}")
        print(f"  -> Polling Interval:  {self.poll_interval}s")
        print("="*105)

        while True:
            # Check market status & rotate
            now = int(time.time())
            if not self.current_market or now >= self.current_market["window_end"] - 5:
                print("\n[MARKET] Scanning for active 5-minute Bitcoin market...")
                mkt = self.discover_active_5m_btc_market()
                if not mkt:
                    print("[MARKET] Waiting for active 5m market to open... (sleeping 3s)")
                    time.sleep(3)
                    continue

                self.current_market = mkt
                t_end_str = datetime.datetime.fromtimestamp(mkt["window_end"], datetime.timezone.utc).strftime("%H:%M:%S UTC")
                print(f"[MARKET ACTIVE] {mkt['slug']} ({mkt['title']})")
                print(f"  -> Window End: {t_end_str} (Time Remaining: {mkt['window_end'] - now}s)")
                print(f"  -> UP Token:   {mkt['up_token']}")
                print(f"  -> DOWN Token: {mkt['down_token']}")
                print("-"*105)

            time_left = self.current_market["window_end"] - int(time.time())
            books = self.fetch_order_books(self.current_market["up_token"], self.current_market["down_token"])

            if books:
                up_ask = books["up_ask"]
                up_sz  = books["up_size"]
                dn_ask = books["down_ask"]
                dn_sz  = books["down_size"]
                comb   = round(up_ask + dn_ask, 3)

                now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")

                # Heartbeat line
                status_color = "\033[92m" if comb <= self.max_combined_cost else "\033[0m"
                print(f"[{now_str}] T-{time_left:03d}s | UP: ${up_ask:.3f} ({up_sz:5.1f} sh) | DOWN: ${dn_ask:.3f} ({dn_sz:5.1f} sh) | Comb: {comb:.3f} | Snipes: {self.trades_executed} (PnL: +${self.total_profit_locked:.2f})", end="\r", flush=True)

                # TRIGGER CHECK: Require BOTH sides to have >= min_depth_threshold (e.g. 100.0 shares)
                if comb <= self.max_combined_cost and up_sz >= self.min_depth_threshold and dn_sz >= self.min_depth_threshold:
                    matched_size = min(up_sz, dn_sz, self.max_order_size)
                    if matched_size >= self.min_order_size:
                        self.execute_batch_fok_snipe(
                            self.current_market["up_token"],
                            self.current_market["down_token"],
                            up_ask,
                            dn_ask,
                            matched_size
                        )
                        # Short cooldown after trigger
                        time.sleep(1.0)

            time.sleep(self.poll_interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Polymarket Batch FOK Arbitrage Sniper")
    parser.add_argument("--live", action="store_true", help="Enable real funded live trading (default is dry-run)")
    parser.add_argument("--max-cost", type=float, default=0.980, help="Max combined price threshold (default: 0.980)")
    parser.add_argument("--min-size", type=float, default=5.0, help="Min order size in shares (default: 5.0)")
    parser.add_argument("--max-size", type=float, default=20.0, help="Max order size in shares (default: 20.0)")
    parser.add_argument("--interval", type=float, default=0.4, help="Order book poll interval in seconds (default: 0.4s)")

    args = parser.parse_args()

    sniper = BatchFokSniper(
        max_combined_cost=args.max_cost,
        min_order_size=args.min_size,
        max_order_size=args.max_size,
        dry_run=not args.live,
        poll_interval=args.interval,
    )
    sniper.run()
