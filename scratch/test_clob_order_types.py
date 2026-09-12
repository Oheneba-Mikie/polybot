import os
import sys
import json
import time

sys.stdout.reconfigure(encoding='utf-8')

print("="*95)
print("🔍 TESTING POLYMARKET CLOB ORDER METHODS FOR T-12s")
print("="*95)

from py_clob_client_v2 import ClobClient, ApiCreds, OrderArgs, MarketOrderArgsV2, OrderType

# Check methods available on client
print("Checking py_clob_client_v2 signature and order methods...")
print("OrderArgs fields:", OrderArgs.__annotations__ if hasattr(OrderArgs, '__annotations__') else dir(OrderArgs))
print("="*95)
