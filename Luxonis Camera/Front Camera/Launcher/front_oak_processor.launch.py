from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """
    Launch file for the front OAK-D W processor node.

    Assumes:
      - A Luxonis depthai-ros node is already running and publishing a stereo
        point cloud on /stereo/points and NN detections on /nn/detections
        (adjust these if your actual topics differ).

    This launch file:
      - Starts the front_oak_processor node.
      - Remaps Luxonis topics into the standardized /front/... namespace.
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
            }],
            remappings=[
                # Map Luxonis stereo pointcloud to what front_oak_node expects.
                # Left side = topic used inside front_oak_node.py
                # Right side = topic actually published by depthai-ros.
                ('/front/camera/points', '/stereo/points'),

                # Adjust this if your NN detections topic has a different name.
                ('/front/nn/detections', '/nn/detections'),
            ],
        ),
    ])