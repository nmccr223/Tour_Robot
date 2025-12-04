#!/usr/bin/env python3
"""
Navigation POC Launch File
--------------------------
Launches the SER8 navigation proof-of-concept system.

This assumes:
- CM5 is running ldlidar_stl_ros2 and publishing /scan
- SER8 has network connectivity to CM5
- Motor controllers are connected via USB (optional)

Usage:
    ros2 launch navigation_poc.launch.py
    
    # With motors enabled (CAUTION):
    ros2 launch navigation_poc.launch.py enable_motors:=true
    
    # Custom safety parameters:
    ros2 launch navigation_poc.launch.py safe_distance:=2.0 max_speed:=0.3
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # Launch arguments
    enable_motors_arg = DeclareLaunchArgument(
        'enable_motors',
        default_value='false',
        description='Enable motor control (CAUTION: robot will move!)'
    )
    
    max_linear_speed_arg = DeclareLaunchArgument(
        'max_linear_speed',
        default_value='0.5',
        description='Maximum linear speed in m/s'
    )
    
    max_angular_speed_arg = DeclareLaunchArgument(
        'max_angular_speed',
        default_value='1.0',
        description='Maximum angular speed in rad/s'
    )
    
    safe_distance_arg = DeclareLaunchArgument(
        'safe_distance',
        default_value='1.5',
        description='Safe distance from obstacles in meters'
    )
    
    danger_distance_arg = DeclareLaunchArgument(
        'danger_distance',
        default_value='0.5',
        description='Danger zone distance in meters (emergency stop)'
    )
    
    # Navigation POC node
    navigation_node = Node(
        package='main_control',
        executable='navigation_poc',
        name='navigation_poc',
        output='screen',
        parameters=[{
            'enable_motors': LaunchConfiguration('enable_motors'),
            'max_linear_speed': LaunchConfiguration('max_linear_speed'),
            'max_angular_speed': LaunchConfiguration('max_angular_speed'),
            'safe_distance': LaunchConfiguration('safe_distance'),
            'danger_distance': LaunchConfiguration('danger_distance'),
        }],
        remappings=[
            # Remap if needed (default /scan should work)
        ]
    )
    
    # Warning log if motors enabled
    motors_warning = LogInfo(
        msg=[
            '\n',
            '=' * 60, '\n',
            'NAVIGATION POC STARTED\n',
            '=' * 60, '\n',
            'Motors enabled: ', LaunchConfiguration('enable_motors'), '\n',
            'Max linear speed: ', LaunchConfiguration('max_linear_speed'), ' m/s\n',
            'Max angular speed: ', LaunchConfiguration('max_angular_speed'), ' rad/s\n',
            'Safe distance: ', LaunchConfiguration('safe_distance'), ' m\n',
            'Danger distance: ', LaunchConfiguration('danger_distance'), ' m\n',
            '=' * 60, '\n',
            'Monitoring topics:\n',
            '  /robot_status - Robot state and performance\n',
            '  /obstacle_detection - Obstacle zones and distances\n',
            '  /cmd_vel - Velocity commands\n',
            '  /scan - LiDAR data (from CM5)\n',
            '=' * 60, '\n'
        ]
    )
    
    return LaunchDescription([
        enable_motors_arg,
        max_linear_speed_arg,
        max_angular_speed_arg,
        safe_distance_arg,
        danger_distance_arg,
        motors_warning,
        navigation_node,
    ])
