import os, sys, time, subprocess, socket

# Kill any existing process on port 8080
def kill_port_8080():
    try:
        cmd = 'powershell -Command "Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"'
        subprocess.run(cmd, shell=True)
    except Exception as e:
        print("Kill error:", e)

kill_port_8080()
time.sleep(1)

# Verify port is free
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind(('0.0.0.0', 8080))
    s.close()
    print("Port 8080 is verified FREE")
except Exception as e:
    print("Port 8080 still in use:", e)
