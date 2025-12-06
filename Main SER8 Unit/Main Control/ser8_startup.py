#!/usr/bin/env python3
"""
SER8 Startup Orchestrator
-------------------------
Run on SER8 to:
 1) Verify CM5 connectivity and required services.
 2) Verify PLC/motor host reachability.
 3) Verify ROS 2 availability and /scan visibility.
 4) Launch the tour-robot bringup (system_bringup.launch.py).
 5) Confirm core nodes are up before allowing motion.

Usage examples:
  python3 ser8_startup.py \
      --cm5-host 192.168.10.20 --cm5-user tourrobot \
      --services ld19.service ld19-stack.service \
      --motor-host 192.168.10.2 --motor-port 5005

  python3 ser8_startup.py --no-launch   # Only run checks, do not launch

Notes:
- Assumes passwordless SSH from SER8 to CM5 for service checks/restarts.
- Assumes sudoers on CM5 allows the specified user to run systemctl without a password,
  or you skip restarts with --no-restart.
- Requires ROS 2 environment sourced (or set --ros-setup to the setup.bash path).
"""

import argparse
import os
import socket
import subprocess
import sys
import time
from typing import List


DEFAULT_SERVICES = ["ld19.service", "ld19-stack.service"]
REQUIRED_NODES = ["/main_controller", "/front_oak_processor", "/rear_oak_processor"]
REQUIRED_TOPICS = ["/scan"]


def run(cmd: List[str], env=None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def ping_host(host: str, timeout: int = 2) -> bool:
    # Linux ping: -c 1 (count) -W timeout seconds
    proc = run(["ping", "-c", "1", "-W", str(timeout), host])
    return proc.returncode == 0


def check_tcp(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def ssh(cmd: str, host: str, user: str, ssh_opts: List[str]) -> subprocess.CompletedProcess:
    full = ["ssh", *ssh_opts, f"{user}@{host}", cmd]
    return run(full)


def service_active(service: str, host: str, user: str, ssh_opts: List[str]) -> bool:
    proc = ssh(f"systemctl is-active {service}", host, user, ssh_opts)
    return proc.returncode == 0 and proc.stdout.strip() == "active"


def service_restart(service: str, host: str, user: str, ssh_opts: List[str]) -> bool:
    proc = ssh(f"sudo systemctl restart {service}", host, user, ssh_opts)
    return proc.returncode == 0


def ensure_ros_env(ros_setup: str | None):
    if ros_setup:
        if not os.path.exists(ros_setup):
            sys.exit(f"ROS setup script not found: {ros_setup}")
        # Use a login shell to source and print env
        cmd = f"bash -lc 'source {ros_setup} && env'"
        env_proc = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        if env_proc.returncode != 0:
            sys.exit(f"Failed to source ROS setup: {env_proc.stderr.strip()}")
        env = os.environ.copy()
        for line in env_proc.stdout.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
        return env
    return os.environ.copy()


def ros2_available(env) -> bool:
    proc = run(["ros2", "--version"], env=env)
    return proc.returncode == 0


def ros2_list_nodes(env) -> List[str]:
    proc = run(["ros2", "node", "list"], env=env)
    if proc.returncode != 0:
        return []
    return proc.stdout.strip().splitlines()


def ros2_list_topics(env) -> List[str]:
    proc = run(["ros2", "topic", "list"], env=env)
    if proc.returncode != 0:
        return []
    return proc.stdout.strip().splitlines()


def start_launch(env) -> subprocess.Popen:
    # Use ros2 launch main_control system_bringup.launch.py
    return subprocess.Popen(
        ["ros2", "launch", "main_control", "system_bringup.launch.py"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def wait_for_nodes(env, nodes: List[str], timeout: int = 20) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        present = set(ros2_list_nodes(env))
        if all(n in present for n in nodes):
            return True
        time.sleep(1.0)
    return False


def wait_for_topics(env, topics: List[str], timeout: int = 15) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        present = set(ros2_list_topics(env))
        if all(t in present for t in topics):
            return True
        time.sleep(1.0)
    return False


def main():
    parser = argparse.ArgumentParser(description="SER8 startup orchestrator")
    parser.add_argument("--cm5-host", required=True, help="CM5 IP/hostname")
    parser.add_argument("--cm5-user", required=True, help="CM5 SSH user")
    parser.add_argument("--services", nargs="*", default=DEFAULT_SERVICES, help="Services to check on CM5")
    parser.add_argument("--motor-host", required=True, help="PLC/motor host")
    parser.add_argument("--motor-port", type=int, default=5005, help="PLC/motor port")
    parser.add_argument("--ros-setup", help="Path to ROS setup.bash to source (optional)")
    parser.add_argument("--no-restart", action="store_true", help="Do not attempt to restart services on CM5")
    parser.add_argument("--no-launch", action="store_true", help="Run checks only; do not launch bringup")
    parser.add_argument("--ssh-opts", nargs="*", default=["-o", "BatchMode=yes", "-o", "ConnectTimeout=3", "-o", "StrictHostKeyChecking=accept-new"],
                        help="Additional ssh options")
    args = parser.parse_args()

    # 0) ROS env
    env = ensure_ros_env(args.ros_setup)
    if not ros2_available(env):
        sys.exit("ros2 not available in PATH. Source setup or pass --ros-setup")

    # 1) Network reachability
    print(f"Checking CM5 reachability ({args.cm5_host})...")
    if not ping_host(args.cm5_host):
        sys.exit("CM5 not reachable (ping failed)")

    # 2) Check CM5 services
    for svc in args.services:
        if service_active(svc, args.cm5_host, args.cm5_user, args.ssh_opts):
            print(f"OK    {svc} active on CM5")
            continue
        if args.no_restart:
            sys.exit(f"Service {svc} not active on CM5 and --no-restart set")
        print(f"WARN  {svc} not active; attempting restart...")
        if not service_restart(svc, args.cm5_host, args.cm5_user, args.ssh_opts):
            sys.exit(f"Failed to restart {svc} on CM5 (SSH/sudo/systemctl issue)")
        time.sleep(1)
        if not service_active(svc, args.cm5_host, args.cm5_user, args.ssh_opts):
            sys.exit(f"Service {svc} still not active after restart")
        print(f"OK    {svc} restarted and active")

    # 3) Motor host reachability
    print(f"Checking motor host {args.motor_host}:{args.motor_port} ...")
    if not check_tcp(args.motor_host, args.motor_port, timeout=2.0):
        sys.exit("Motor host/port not reachable")
    print("OK    Motor host reachable")

    # 4) ROS topics (/scan) visible
    print("Checking /scan topic visibility...")
    if not wait_for_topics(env, REQUIRED_TOPICS, timeout=10):
        sys.exit("/scan topic not found; ensure CM5 LiDAR is publishing")
    print("OK    /scan detected")

    if args.no_launch:
        print("Checks complete; skipping launch (--no-launch)")
        return 0

    # 5) Launch bringup
    print("Starting system_bringup.launch.py ...")
    launch_proc = start_launch(env)
    time.sleep(2)  # brief head start

    # 6) Confirm nodes come up
    if not wait_for_nodes(env, REQUIRED_NODES, timeout=25):
        launch_proc.terminate()
        sys.exit("Required nodes did not appear; bringup aborted")
    print("OK    Required nodes are running")

    print("System bringup succeeded. Monitor logs below (Ctrl+C to stop):")
    try:
        # Stream launch stdout/stderr
        while True:
            line = launch_proc.stdout.readline()
            if not line:
                if launch_proc.poll() is not None:
                    break
                time.sleep(0.1)
                continue
            sys.stdout.write(line)
            sys.stdout.flush()
    except KeyboardInterrupt:
        print("Stopping bringup...")
        launch_proc.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
