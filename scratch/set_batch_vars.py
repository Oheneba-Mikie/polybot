import subprocess
import os

env_vars = {
    "POLYMARKET_ADDRESS": "0x81ad69942a32f7b1df4d16f0c3f79311f55de50a",
    "POLYMARKET_PRIVATE_KEY": "0x9eff1c11ba151e32d0e632b72c6d3ca6f77593493da50e56dc820a95515a3fc7",
    "POLYMARKET_API_KEY": "43f60963-1561-bd62-579b-a0573aa7aaa2",
    "POLYMARKET_API_SECRET": "1CvrOLIcfDIID4Nm2wmGzIh_m_dJgiWfJsFE7HvEKSk=",
    "POLYMARKET_PASSPHRASE": "a6970deebfd5851c3991c4e1e1336654a485cd658354bb341bbb67ba05db56b5",
    "DRY_RUN": "false",
    "TARGET_TOTAL_COST": "0.960",
    "REQUIRED_SHARES": "5.0",
    "PORT": "8080"
}

service_id = "92085ee6-62ab-463d-a313-cab77706a35c"

for k, v in env_vars.items():
    cmd = f'railway variable --set "{k}={v}" -s {service_id} -e production'
    res = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    print(f"Set {k}: {res.stdout.strip() or res.stderr.strip()}")

print("All variables set successfully on batch-arb-bot!")
