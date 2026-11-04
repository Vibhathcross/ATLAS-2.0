import os
import sys
import time
import socket
import traceback
import urllib.request
from pathlib import Path
import psutil
import uvicorn

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Ensure stdout and stderr exist even under pythonw.exe
LOG_DIR = BASE_DIR / "data"
LOG_DIR.mkdir(parents=True, exist_ok=True)

if sys.stdout is None or not hasattr(sys.stdout, "write"):
    sys.stdout = open(LOG_DIR / "atlas_stdout.log", "a", encoding="utf-8", buffering=1)
if sys.stderr is None or not hasattr(sys.stderr, "write"):
    sys.stderr = open(LOG_DIR / "atlas_stderr.log", "a", encoding="utf-8", buffering=1)

from backend.app import launch_app_window

def is_server_alive(port: int = 8000) -> bool:
    """Verify if ATLAS server is already healthy and responding to HTTP requests."""
    try:
        url = f"http://127.0.0.1:{port}/api/config"
        req = urllib.request.Request(url, headers={"User-Agent": "ATLAS-HealthCheck"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False

def is_port_in_use(port: int = 8000) -> bool:
    """Check if the TCP port is already bound."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0

def free_port_if_stale(port: int = 8000) -> bool:
    """
    If port is bound but HTTP healthcheck failed, it's a stale or frozen process.
    Find and safely terminate it to avoid [Errno 10048] address conflict.
    """
    current_pid = os.getpid()
    cleared = False
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['pid'] == current_pid:
                continue
            try:
                for conn in proc.net_connections(kind='inet'):
                    if conn.laddr.port == port:
                        print(f"Clearing stale process {proc.info['name']} (PID: {proc.info['pid']}) holding port {port}...")
                        proc.kill()
                        proc.wait(timeout=2)
                        cleared = True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        print(f"Warning during stale port cleanup: {e}")
    return cleared

def main():
    try:
        port = 8000
        
        # Scenario 1: ATLAS server is already running and healthy
        if is_server_alive(port):
            print(f"ATLAS 2.0 is already active on port {port}. Focusing application window...")
            launch_app_window(f"http://127.0.0.1:{port}")
            sys.exit(0)

        # Scenario 2: Port is occupied but server is dead or unresponsive
        if is_port_in_use(port):
            print(f"Port {port} is occupied by an unresponsive process. Cleaning up...")
            free_port_if_stale(port)
            time.sleep(0.5)

        # Start uvicorn with automatic fallback to port 8001 if 8000 cannot be bound
        try:
            uvicorn.run("backend.app:app", host="127.0.0.1", port=port, log_level="info")
        except OSError as e:
            if e.errno == 10048 or "10048" in str(e):
                fallback_port = 8001
                print(f"Port {port} conflict encountered. Falling back to port {fallback_port}...")
                free_port_if_stale(fallback_port)
                uvicorn.run("backend.app:app", host="127.0.0.1", port=fallback_port, log_level="info")
            else:
                raise
    except Exception:
        with open(LOG_DIR / "atlas_crash.log", "a", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        raise

if __name__ == "__main__":
    main()
