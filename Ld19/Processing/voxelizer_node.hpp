#pragma once

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <robot_msgs/msg/lidar_scan_summary.hpp>

namespace lidar_preprocess
{

class VoxelizerNode : public rclcpp::Node
{
public:
  explicit VoxelizerNode(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());

private:
  void rawCallback(const sensor_msgs::msg::PointCloud2::SharedPtr msg);

  void computeSummary(const sensor_msgs::msg::PointCloud2 & cloud,
                      robot_msgs::msg::LidarScanSummary & summary);

  rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr raw_sub_;
  rclcpp::Publisher<sensor_msgs::msg::PointCloud2>::SharedPtr cloud_pub_;
  rclcpp::Publisher<robot_msgs::msg::LidarScanSummary>::SharedPtr summary_pub_;

  // Parameters
  double voxel_leaf_size_;
  double min_range_;
  double max_range_;
  int num_sectors_;
};

}  // namespace lidar_preprocess