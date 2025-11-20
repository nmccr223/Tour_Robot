# rear_oak_processor/launch/rear_oak_processor.launch.py
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """
    Launch file for the rear OAK-D Lite processor node.

    Assumes:
      - A Luxonis depthai-ros node is running and publishing a stereo
        point cloud on /stereo/points (or another topic you confirm).
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
            }],
            remappings=[
                # Map Luxonis pointcloud to what rear_oak_node expects.
                ('/rear/camera/points', '/stereo/points'),
                # Adjust if you later enable NN for the rear camera.
                ('/rear/nn/detections', '/nn/detections'),
            ],
        ),
    ])