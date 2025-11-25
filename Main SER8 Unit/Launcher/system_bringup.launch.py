from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    """System bringup launch file for the SER8 tour robot.

    This starts:
      - Main controller node on the SER8
      - Front OAK-D W processor node on the SER8
      - Rear OAK-D Lite processor node on the SER8

    DepthAI camera drivers (depthai-ros) should be launched separately
    or added here later once their package/topic details are finalized.
    """

    main_control_node = Node(
        package="main_control",
        executable="main_controller_node",
        name="main_controller",
        output="screen",
        parameters=[
            {
                "control_rate_hz": 20.0,
                "hard_stop_distance": 0.4,
                "slow_down_distance": 1.0,
                "max_linear_speed": 0.4,
                "max_angular_speed": 0.8,
                "motor_host": "192.168.10.2",
                "motor_port": 5005,
                "use_cmd_vel_topic": False,
            }
        ],
    )

    front_oak_processor_node = Node(
        package="front_oak_processor",
        executable="front_oak_node",
        name="front_oak_processor",
        output="screen",
        parameters=[
            {
                "fov_deg": 60.0,
                "max_distance": 5.0,
                "person_label": "person",
            }
        ],
        # Remap these once actual DepthAI topics are confirmed.
        remappings=[
            ("/front/camera/points", "/stereo/points"),
            ("/front/nn/detections", "/nn/detections"),
        ],
    )

    rear_oak_processor_node = Node(
        package="rear_oak_processor",
        executable="rear_oak_node",
        name="rear_oak_processor",
        output="screen",
        parameters=[
            {
                "fov_deg": 90.0,
                "max_distance": 3.0,
                "person_label": "person",
                "frame_skip": 0,
            }
        ],
        # Remap these once actual DepthAI topics are confirmed.
        remappings=[
            ("/rear/camera/points", "/stereo/points"),
            ("/rear/nn/detections", "/nn/detections"),
        ],
    )

    return LaunchDescription([
        main_control_node,
        front_oak_processor_node,
        rear_oak_processor_node,
    ])
