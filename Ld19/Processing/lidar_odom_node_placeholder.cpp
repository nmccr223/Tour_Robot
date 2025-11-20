#include "lidar_odom/lidar_odom_node.hpp"

#include <geometry_msgs/msg/quaternion.hpp>

using std::placeholders::_1;

namespace lidar_odom
{

LidarOdomNode::LidarOdomNode(const rclcpp::NodeOptions & options)
: Node("lidar_odom", options),
  x_(0.0), y_(0.0), yaw_(0.0)
{
  rclcpp::QoS sensor_qos{rclcpp::SensorDataQoS().keep_last(5)};
  cloud_sub_ = this->create_subscription<sensor_msgs::msg::PointCloud2>(
    "/ld19/pointcloud", sensor_qos, std::bind(&LidarOdomNode::cloudCallback, this, _1));

  odom_pub_ = this->create_publisher<nav_msgs::msg::Odometry>(
    "/ld19/lidar_odom", rclcpp::QoS(1).reliable());

  RCLCPP_INFO(this->get_logger(), "LidarOdomNode initialized (placeholder)");
}

void LidarOdomNode::cloudCallback(const sensor_msgs::msg::PointCloud2::SharedPtr msg)
{
  // TODO: implement actual scan-matching / odometry here

  nav_msgs::msg::Odometry odom;
  odom.header.stamp = msg->header.stamp;
  odom.header.frame_id = "odom";       // or "map"
  odom.child_frame_id = "base_link";   // or "lidar_link" if you prefer

  odom.pose.pose.position.x = x_;
  odom.pose.pose.position.y = y_;
  odom.pose.pose.position.z = 0.0;

  // trivial orientation = zero yaw (placeholder)
  odom.pose.pose.orientation.w = 1.0;
  odom.pose.pose.orientation.x = 0.0;
  odom.pose.pose.orientation.y = 0.0;
  odom.pose.pose.orientation.z = 0.0;

  // Covariances: set something large to indicate uncertainty (placeholder)
  odom.pose.covariance[0] = 0.5;
  odom.pose.covariance[7] = 0.5;
  odom.pose.covariance[35] = 0.5;

  odom_pub_->publish(odom);
}

}  // namespace lidar_odom

#include "rclcpp_components/register_node_macro.hpp"
RCLCPP_COMPONENTS_REGISTER_NODE(lidar_odom::LidarOdomNode)