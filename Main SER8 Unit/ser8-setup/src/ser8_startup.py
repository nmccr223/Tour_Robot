# ser8_startup.py

import os
import subprocess
import argparse

def start_tour_robot(cm5_host, cm5_user, services):
    # Check if ROS is sourced
    ros_setup_path = '/opt/ros/jazzy/setup.bash'
    if not os.path.exists(ros_setup_path):
        print("ROS is not installed or the setup file is missing.")
        return

    # Source ROS environment
    subprocess.call(['bash', '-c', f'source {ros_setup_path}'])

    # Start services
    for service in services:
        print(f"Starting service: {service}")
        subprocess.call(['ssh', f'{cm5_user}@{cm5_host}', f'sudo systemctl start {service}'])

    print("Tour Robot system started successfully.")

def main():
    parser = argparse.ArgumentParser(description='Start the Tour Robot system.')
    parser.add_argument('--cm5-host', type=str, required=True, help='IP address of the CM5')
    parser.add_argument('--cm5-user', type=str, required=True, help='Username for CM5')
    parser.add_argument('--services', nargs='+', required=True, help='List of services to start')

    args = parser.parse_args()

    start_tour_robot(args.cm5_host, args.cm5_user, args.services)

if __name__ == '__main__':
    main()