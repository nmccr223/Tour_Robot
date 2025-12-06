#!/usr/bin/env python3
"""
CM5 Service Watchdog
--------------------
Run on SER8 to verify required systemd services on the CM5 are active.
If a service is inactive/failed, the watchdog attempts to start it via SSH.

Prerequisites (run once on SER8):
  - Passwordless SSH to CM5 (ssh-keygen + ssh-copy-id)
  - SER8 user must be allowed to run systemctl on CM5 (sudoers or passwordless sudo for systemctl)

Usage examples:
  # Single check
  python3 cm5_service_watchdog.py

  # Continuous check every 60s
  python3 cm5_service_watchdog.py --loop 60
"""

import argparse
import subprocess
import sys
import time
from typing import List

# --- CONFIGURE THESE ---
CM5_HOST = "192.168.10.20"      # IP/hostname of CM5
CM5_USER = "tourrobot"          # SSH user on CM5
SERVICES: List[str] = [          # Services to watch on CM5
    "ld19.service",
    "ld19-stack.service",
]
SSH_OPTS = [
    "-o", "BatchMode=yes",          # Fail fast if key not set
    "-o", "ConnectTimeout=3",      # Short connect timeout
    "-o", "StrictHostKeyChecking=accept-new",
]
# -----------------------


def run_ssh(cmd: str) -> subprocess.CompletedProcess:
    """Run an SSH command on CM5 and return the completed process."""
    full_cmd = ["ssh", *SSH_OPTS, f"{CM5_USER}@{CM5_HOST}", cmd]
    return subprocess.run(full_cmd, capture_output=True, text=True)


def is_service_active(service: str) -> bool:
    """Return True if systemd reports the service as active."""
    proc = run_ssh(f"systemctl is-active {service}")
    if proc.returncode == 0 and proc.stdout.strip() == "active":
        return True
    return False


def restart_service(service: str) -> bool:
    """Attempt to restart the given service on CM5."""
    proc = run_ssh(f"sudo systemctl restart {service}")
    return proc.returncode == 0


def check_once() -> int:
    """Check all services once; restart if needed. Returns number restarted."""
    restarted = 0
    for svc in SERVICES:
        if is_service_active(svc):
            print(f"OK    {svc} is active")
            continue
        print(f"WARN  {svc} not active; attempting restart...")
        if restart_service(svc):
            # Recheck after restart
            time.sleep(1)
            if is_service_active(svc):
                print(f"INFO  {svc} restarted successfully")
            else:
                print(f"ERROR {svc} restart issued but still not active")
            restarted += 1
        else:
            print(f"ERROR Failed to restart {svc} (SSH/sudo/systemctl issue)")
    return restarted


def main() -> int:
    parser = argparse.ArgumentParser(description="Watchdog for CM5 services from SER8")
    parser.add_argument("--loop", type=int, default=0,
                        help="If >0, run in a loop with given interval (seconds)")
    args = parser.parse_args()

    if args.loop <= 0:
        restarted = check_once()
        return 0 if restarted == 0 else 1

    try:
        while True:
            restarted = check_once()
            # Non-zero exit code would terminate the loop; keep running
            time.sleep(args.loop)
    except KeyboardInterrupt:
        print("Stopping watchdog loop")
        return 0


if __name__ == "__main__":
    sys.exit(main())
