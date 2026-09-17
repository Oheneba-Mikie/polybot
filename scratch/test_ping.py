import requests, time

for i in range(10):
    try:
        res = requests.get("http://127.0.0.1:8080/api/state", timeout=2)
        if res.status_code == 200:
            d = res.json()
            print("ONLINE!")
            print("Market:", d.get("current_candle_slug"))
            print("Time Rem:", d.get("seconds_remaining"), "s")
            print("Status:", d.get("status").encode('ascii', 'ignore').decode('ascii'))
            print("Crosses:", len(d.get("cross_opportunities", [])))
            break
    except Exception as e:
        time.sleep(1)
else:
    print("Failed to reach server")
