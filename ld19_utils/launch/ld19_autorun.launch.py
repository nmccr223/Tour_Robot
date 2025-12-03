from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    port = LaunchConfiguration('port', default='/dev/ld19')
    frame_id = LaunchConfiguration('frame_id', default='base_laser')
    topic_name = LaunchConfiguration('topic_name', default='scan')
    baud = LaunchConfiguration('baud', default='230400')

    driver_node = Node(
        package='ldlidar_stl_ros2',
        executable='ldlidar_stl_ros2_node',
        name='ldlidar_driver',
        output='screen',
        parameters=[{
            'product_name': 'LDLiDAR_LD19',
            'topic_name': topic_name,
            'port_name': port,
            'port_baudrate': baud,
            'frame_id': frame_id,
            'laser_scan_dir': False,
        }],
    )

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
        DeclareLaunchArgument('port', default_value='/dev/ld19', description='Serial port or symlink for LD19'),
        DeclareLaunchArgument('frame_id', default_value='base_laser', description='Laser frame id'),
        DeclareLaunchArgument('topic_name', default_value='scan', description='Scan topic name'),
        DeclareLaunchArgument('baud', default_value='230400', description='Serial baudrate'),
        DeclareLaunchArgument('remap_scan', default_value='/scan', description='Remap source scan topic for preprocess'),
        driver_node,
        preprocess_node,
        monitor_node,
    ])
