#pragma once

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <nav_msgs/msg/odometry.hpp>

namespace lidar_odom
{

class LidarOdomNode : public rclcpp::Node
{
public:
  explicit LidarOdomNode(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());

private:
  void cloudCallback(const sensor_msgs::msg::PointCloud2::SharedPtr msg);

  rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr cloud_sub_;
  rclcpp::Publisher<nav_msgs::msg::Odometry>::SharedPtr odom_pub_;

  // Internal state (pose estimate)
  double x_;
  double y_;
  double yaw_;
};

}  // namespace lidar_odom