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
        remappings=[
            ('/ld19/scan', LaunchConfiguration('remap_scan', default='/scan')),
        ],
    )

    monitor_node = Node(
        package='ld19_utils',
        executable='ld19_monitor_node',
        name='ld19_monitor',
        output='screen',
    )

    return LaunchDescription([
        DeclareLaunchArgument('remap_scan', default_value='/scan', description='Remap source scan topic for preprocess'),
        preprocess_node,
        monitor_node,
    ])
