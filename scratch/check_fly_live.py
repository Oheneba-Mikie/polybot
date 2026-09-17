import requests

url = "https://polybot-sniper-mikie.fly.dev/api/state"
try:
    r = requests.get(url, timeout=5)
    print("STATUS CODE:", r.status_code)
    d = r.json()
    print("Market:", d.get("current_candle_slug"))
    print("Time Rem:", d.get("seconds_remaining"))
    print("Combined Cost:", d.get("combined_cost"))
    print("Server Status:", d.get("status").encode('ascii', 'ignore').decode('ascii'))
except Exception as e:
    print("Error:", e)
