import json
import time
import ssl
import sys
import threading
import websocket
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

class ClobWebSocketStream:
    def __init__(self):
        self.ws = None
        self.current_tokens = []
        self.book_cache = {}
        self.is_connected = False
        self.thread = None
        self._running = True

    def update_tokens(self, tokens):
        if set(tokens) == set(self.current_tokens) and self.is_connected:
            return
        self.current_tokens = tokens
        for t in tokens:
            if t not in self.book_cache:
                self.book_cache[t] = {"best_ask": 1.0, "best_ask_size": 0.0, "best_bid": 0.0}
        if self.ws and self.is_connected:
            try:
                sub = {
                    "type": "market",
                    "assets_ids": self.current_tokens,
                    "custom_feature_enabled": True
                }
                self.ws.send(json.dumps(sub))
            except Exception:
                pass

    def start(self):
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        while self._running:
            try:
                def on_open(ws):
                    self.is_connected = True
                    print("⚡ [WS OPEN] Connected to CLOB WS!")
                    if self.current_tokens:
                        sub = {
                            "type": "market",
                            "assets_ids": self.current_tokens,
                            "custom_feature_enabled": True
                        }
                        ws.send(json.dumps(sub))

                def on_message(ws, msg):
                    if msg == "PONG":
                        return
                    try:
                        data = json.loads(msg)
                        if isinstance(data, list):
                            for m in data:
                                aid = str(m.get("asset_id", ""))
                                asks = m.get("asks", [])
                                bids = m.get("bids", [])
                                b_ask = float(min(asks, key=lambda x: float(x["price"]))["price"]) if asks else 1.0
                                b_ask_s = float(min(asks, key=lambda x: float(x["price"]))["size"]) if asks else 0.0
                                b_bid = float(max(bids, key=lambda x: float(x["price"]))["price"]) if bids else 0.0
                                self.book_cache[aid] = {"best_ask": b_ask, "best_ask_size": b_ask_s, "best_bid": b_bid}
                        elif isinstance(data, dict):
                            pcs = data.get("price_changes", [])
                            for pc in pcs:
                                aid = str(pc.get("asset_id", ""))
                                b_ask = float(pc.get("best_ask", 1.0)) if pc.get("best_ask") is not None else 1.0
                                b_bid = float(pc.get("best_bid", 0.0)) if pc.get("best_bid") is not None else 0.0
                                sz = float(pc.get("size", 0.0))
                                if aid in self.book_cache:
                                    self.book_cache[aid]["best_ask"] = b_ask
                                    self.book_cache[aid]["best_bid"] = b_bid
                                    if pc.get("side") == "SELL" or pc.get("best_ask") == pc.get("price"):
                                        self.book_cache[aid]["best_ask_size"] = sz
                                else:
                                    self.book_cache[aid] = {"best_ask": b_ask, "best_ask_size": sz, "best_bid": b_bid}
                    except Exception:
                        pass

                def on_error(ws, err):
                    print("WS ERR:", err)

                def on_close(ws, close_status, close_msg):
                    self.is_connected = False

                self.ws = websocket.WebSocketApp(
                    "wss://ws-subscriptions-clob.polymarket.com/ws/market",
                    on_open=on_open,
                    on_message=on_message,
                    on_error=on_error,
                    on_close=on_close
                )
                self.ws.run_forever(sslopt={"context": ssl_ctx}, ping_interval=10, ping_timeout=5)
            except Exception:
                pass
            time.sleep(1.0)

    def get_prices(self, up_token, down_token):
        up_data = self.book_cache.get(up_token, {"best_ask": 1.0, "best_ask_size": 0.0})
        dn_data = self.book_cache.get(down_token, {"best_ask": 1.0, "best_ask_size": 0.0})
        return up_data["best_ask"], up_data["best_ask_size"], dn_data["best_ask"], dn_data["best_ask_size"]

if __name__ == "__main__":
    w_start = int(time.time() // 300) * 300
    r = requests.get(f"https://gamma-api.polymarket.com/events?slug=eth-updown-5m-{w_start}").json()
    toks = json.loads(r[0]["markets"][0]["clobTokenIds"])
    print("Tokens:", toks)

    stream = ClobWebSocketStream()
    stream.update_tokens(toks)
    stream.start()

    for _ in range(10):
        time.sleep(0.5)
        up_p, up_s, dn_p, dn_s = stream.get_prices(toks[0], toks[1])
        print(f"WS Feed -> UP: ${up_p:.2f} ({up_s:.1f}sh) | DN: ${dn_p:.2f} ({dn_s:.1f}sh) | Comb: ${up_p + dn_p:.3f}")
