from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """
    Launch rear OAK processor with explicit remaps.

    Default remaps assume depthai_ros_driver rgbd_pcl.launch.py publishes:
    - /oak/points
    - /nn/detections

    If your deployment uses different topics, update remappings here or override
    at launch time.
    """
    return LaunchDescription([
        Node(
            package='rear_oak_processor',
            executable='rear_oak_node',
            name='rear_oak_processor',
            output='screen',
            parameters=[{
                'fov_deg': 90.0,
                'max_distance': 3.0,
                'person_label': 'person',
                'frame_skip': 0,
                'input_cloud_topic': '/rear/oak/points',
                'input_detections_topic': '/rear/oak/detections',
                'output_summary_topic': '/rear/oak/summary',
            }],
        ),
    ])
