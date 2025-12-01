# LD19 Utils Package (CM5 Workspace)

Copy this `ld19_utils` directory into `~/cm5_ws/src/` on the CM5.

Expected layout on the CM5:

```text
~/cm5_ws/src/
  ld19_lidar/        # external driver (git clone)
  robot_msgs/        # message package
  ld19_utils/        # this package
```

Then on the CM5:

```bash
cd ~/cm5_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build
source /opt/ros/jazzy/setup.bash
source ~/cm5_ws/install/setup.bash

ros2 run ld19_utils ld19_preprocess_node
ros2 run ld19_utils ld19_monitor_node
```
