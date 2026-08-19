import websocket
import json
import ssl
import time

ws = websocket.WebSocketApp(
    'wss://ws-subscriptions-clob.polymarket.com/ws/market',
    on_message=lambda ws, m: print('MSG:', m[:300]) if 'price_change' in m else None,
    on_open=lambda ws: ws.send(json.dumps({'type': 'market', 'assets_ids': ['114757303102434526685854611598918237937397734185121404179373801201538743126087'], 'custom_feature_enabled': True}))
)
threading_t = __import__('threading').Thread(target=ws.run_forever, kwargs={'sslopt': {'cert_reqs': ssl.CERT_NONE}})
threading_t.start()
time.sleep(4)
ws.close()
