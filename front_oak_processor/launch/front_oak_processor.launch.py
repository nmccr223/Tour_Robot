from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """
    Launch front OAK processor with explicit remaps.

    Default remaps assume depthai_ros_driver rgbd_pcl.launch.py publishes:
    - /oak/points
    - /nn/detections

    If your deployment uses different topics, update remappings here or override
    with command-line remap arguments at launch time.
    """
    return LaunchDescription([
        Node(
            package='front_oak_processor',
            executable='front_oak_node',
            name='front_oak_processor',
            output='screen',
            parameters=[{
                'fov_deg': 60.0,
                'max_distance': 5.0,
                'person_label': 'person',
                'input_cloud_topic': '/front/oak/points',
                'input_detections_topic': '/front/oak/detections',
                'output_summary_topic': '/front/oak/summary',
            }],
        ),
    ])
