from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    """System bringup launch file for the SER8 tour robot.

    This starts:
      - Main controller node on the SER8
      - Front OAK-D W processor node on the SER8
      - Rear OAK-D Lite processor node on the SER8

    Includes the verified Luxonis stack launch that provides PointCloud2:
      - ros2 launch depthai_ros_driver rgbd_pcl.launch.py

    This launch brings up depthai_ros_driver/depthai_filters and
    robot_state_publisher together so /oak/points is available.
    """

    oak_rgbd_pcl_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [FindPackageShare("depthai_ros_driver"), "launch", "rgbd_pcl.launch.py"]
            )
        ),
        # Keep these explicit so camera bringup is deterministic across SER8 units.
        launch_arguments=[
            ("name", "oak"),
            ("camera_model", "OAK-D"),
            ("parent_frame", "oak-d-base-frame"),
            ("cam_pos_x", "0.0"),
            ("cam_pos_y", "0.0"),
            ("cam_pos_z", "0.0"),
            ("cam_roll", "0.0"),
            ("cam_pitch", "0.0"),
            ("cam_yaw", "0.0"),
            ("params_file", "/opt/ros/jazzy/share/depthai_ros_driver/config/rgdb.yaml"),
            ("use_rviz", "False"),
            ("rectify_rgb", "True"),
            ("rs_compat", "False"),
        ],
    )

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
        # Verified PointCloud2 source topic from depthai_ros_driver rgbd_pcl launch.
        remappings=[
            ("/front/camera/points", "/oak/points"),
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
        # Verified PointCloud2 source topic from depthai_ros_driver rgbd_pcl launch.
        remappings=[
            ("/rear/camera/points", "/oak/points"),
            ("/rear/nn/detections", "/nn/detections"),
        ],
    )

    return LaunchDescription([
        oak_rgbd_pcl_launch,
        main_control_node,
        front_oak_processor_node,
        rear_oak_processor_node,
    ])
