# cm5_service_watchdog.py

import subprocess
import time
import os

# Configuration
CM5_HOST = os.getenv('CM5_HOST', '192.168.10.20')
CM5_USER = os.getenv('CM5_USER', 'tourrobot')
SERVICES = ['ld19.service', 'ld19-stack.service']

def check_service_status(service):
    """Check the status of a service on the CM5 system."""
    command = f'ssh {CM5_USER}@{CM5_HOST} systemctl is-active {service}'
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip() == 'active'

def restart_service(service):
    """Restart a service on the CM5 system."""
    command = f'ssh {CM5_USER}@{CM5_HOST} sudo systemctl restart {service}'
    subprocess.run(command, shell=True)

def monitor_services():
    """Monitor the specified services and restart if not active."""
    while True:
        for service in SERVICES:
            if not check_service_status(service):
                print(f"{service} is not active. Restarting...")
                restart_service(service)
            else:
                print(f"{service} is running.")
        time.sleep(60)  # Wait for 60 seconds before checking again

if __name__ == "__main__":
    monitor_services()