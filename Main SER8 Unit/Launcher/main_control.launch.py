# main_control/launch/main_control.launch.py
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='main_control',
            executable='main_controller_node',
            name='main_controller',
            output='screen',
            parameters=[{
                'control_rate_hz': 20.0,
                'hard_stop_distance': 0.4,
                'slow_down_distance': 1.0,
                'max_linear_speed': 0.4,
                'max_angular_speed': 0.8,
                'motor_host': '192.168.10.2',
                'motor_port': 5005,
                'use_cmd_vel_topic': False,
            }]
        )
    ])