import requests, json, datetime

r = requests.get('https://gamma-api.polymarket.com/events?slug=eth-updown-5m-1789326600')
cid = None
if r.status_code == 200:
    data = r.json()
    markets = data[0].get('markets', []) if isinstance(data, list) and data else []
    if markets:
        cid = markets[0].get('conditionId')

print('CID:', cid)
if cid:
    t_url = f'https://data-api.polymarket.com/trades?market={cid}&limit=200'
    tr = requests.get(t_url)
    trades = tr.json() if tr.status_code == 200 else []
    print(f"Total trades in 19:05 candle: {len(trades)}")
    for t in reversed(trades):
        ts = t.get('timestamp')
        dt = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime('%H:%M:%S')
        if '19:08' in dt or '19:09' in dt:
            outcome = t.get('outcome')
            side = t.get('side')
            size = t.get('size')
            price = t.get('price')
            proxy = t.get('proxyWallet', '')
            name = t.get('pseudonym') or t.get('name') or proxy[:8]
            print(f"{dt} | {outcome:4s} | {side:4s} | {size:6.1f}sh @ ${price:.2f} | Buyer/Maker: {name}")
