from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='lidar_preprocess',
            executable='ld19_preprocess_node',  # if using a standalone executable
            # or use composable nodes; adjust as needed
            name='ld19_preprocess',
            output='screen',
            parameters=[{
                'voxel_leaf_size': 0.05,
                'min_range': 0.05,
                'max_range': 10.0,
                'num_sectors': 36,
            }]
        )
    ])