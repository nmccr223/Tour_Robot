from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    preprocess_node = Node(
        package='ld19_utils',
        executable='ld19_preprocess_node',
        name='ld19_preprocess',
        output='screen',
        parameters=[{
            'input_scan_topic': LaunchConfiguration('raw_scan_topic'),
            'output_scan_topic': LaunchConfiguration('filtered_scan_topic'),
            'blocked_center_deg': LaunchConfiguration('blocked_center_deg'),
            'blocked_half_width_deg': LaunchConfiguration('blocked_half_width_deg'),
            'blocked_extra_margin_deg': LaunchConfiguration('blocked_extra_margin_deg'),
            'min_valid_range_m': LaunchConfiguration('min_valid_range_m'),
        }],
        remappings=[
            ('/ld19/scan', LaunchConfiguration('raw_scan_topic')),
        ],
    )

    monitor_node = Node(
        package='ld19_utils',
        executable='ld19_monitor_node',
        name='ld19_monitor',
        output='screen',
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'raw_scan_topic',
            default_value='/scan_raw',
            description='Raw LD19 driver topic consumed by preprocess',
        ),
        DeclareLaunchArgument(
            'filtered_scan_topic',
            default_value='/scan',
            description='Filtered output scan topic for downstream consumers',
        ),
        DeclareLaunchArgument(
            'blocked_center_deg',
            default_value='180.0',
            description='Center angle of blocked sector in robot frame (deg)',
        ),
        DeclareLaunchArgument(
            'blocked_half_width_deg',
            default_value='90.0',
            description='Half width of blocked sector in deg (90 => rear 180)',
        ),
        DeclareLaunchArgument(
            'blocked_extra_margin_deg',
            default_value='0.0',
            description='Additional blocked margin around blocked_half_width_deg',
        ),
        DeclareLaunchArgument(
            'min_valid_range_m',
            default_value='0.0',
            description='Optional minimum valid range threshold; smaller values are masked',
        ),
        preprocess_node,
        monitor_node,
    ])
