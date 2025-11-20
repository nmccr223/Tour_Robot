#include "lidar_preprocess/voxelizer_node.hpp"

#include <limits>
#include <cmath>

#include <sensor_msgs/msg/point_cloud2.hpp>
#include <sensor_msgs/point_cloud2_iterator.hpp>
#include <robot_msgs/msg/lidar_scan_summary.hpp>

using std::placeholders::_1;

namespace lidar_preprocess
{

VoxelizerNode::VoxelizerNode(const rclcpp::NodeOptions & options)
: Node("ld19_preprocess", options)
{
  voxel_leaf_size_ = this->declare_parameter<double>("voxel_leaf_size", 0.05);
  min_range_ = this->declare_parameter<double>("min_range", 0.05);
  max_range_ = this->declare_parameter<double>("max_range", 10.0);
  num_sectors_ = this->declare_parameter<int>("num_sectors", 36);

  rclcpp::QoS sensor_qos{rclcpp::SensorDataQoS().keep_last(5)};
  raw_sub_ = this->create_subscription<sensor_msgs::msg::PointCloud2>(
    "/ld19/raw_scan", sensor_qos, std::bind(&VoxelizerNode::rawCallback, this, _1));

  cloud_pub_ = this->create_publisher<sensor_msgs::msg::PointCloud2>(
    "/ld19/pointcloud", sensor_qos);
  summary_pub_ = this->create_publisher<robot_msgs::msg::LidarScanSummary>(
    "/ld19/summary", rclcpp::QoS(1).reliable());

  RCLCPP_INFO(this->get_logger(), "LD19 VoxelizerNode initialized");
}

void VoxelizerNode::rawCallback(const sensor_msgs::msg::PointCloud2::SharedPtr msg)
{
  // TODO: apply real voxel grid/downsampling here using PCL or your own routine.
  // For now, just forward the input as "downsampled".
  auto downsampled = *msg;

  // Compute summary
  robot_msgs::msg::LidarScanSummary summary;
  computeSummary(downsampled, summary);

  cloud_pub_->publish(downsampled);
  summary_pub_->publish(summary);
}

void VoxelizerNode::computeSummary(const sensor_msgs::msg::PointCloud2 & cloud,
                                   robot_msgs::msg::LidarScanSummary & summary)
{
  summary.stamp = cloud.header.stamp;
  summary.frame_id = cloud.header.frame_id;

  summary.min_range = std::numeric_limits<float>::infinity();
  summary.max_range = 0.0f;
  double sum = 0.0;
  uint32_t count = 0;

  summary.sector_min_ranges.assign(num_sectors_, std::numeric_limits<float>::infinity());

  sensor_msgs::PointCloud2ConstIterator<float> iter_x(cloud, "x");
  sensor_msgs::PointCloud2ConstIterator<float> iter_y(cloud, "y");
  sensor_msgs::PointCloud2ConstIterator<float> iter_z(cloud, "z");

  for (; iter_x != iter_x.end(); ++iter_x, ++iter_y, ++iter_z)
  {
    const float x = *iter_x;
    const float y = *iter_y;

    const float r = std::sqrt(x * x + y * y);
    if (r < min_range_ || r > max_range_) {
      continue;
    }

    if (r < summary.min_range) summary.min_range = r;
    if (r > summary.max_range) summary.max_range = r;
    sum += r;
    ++count;

    // sector index in [-pi, pi]
    const float theta = std::atan2(y, x);
    int idx = static_cast<int>(std::floor((theta + static_cast<float>(M_PI)) /
                                          (2.0f * static_cast<float>(M_PI)) * num_sectors_));
    if (idx < 0) idx = 0;
    if (idx >= num_sectors_) idx = num_sectors_ - 1;

    if (r < summary.sector_min_ranges[idx]) {
      summary.sector_min_ranges[idx] = r;
    }
  }

  summary.num_points = count;
  summary.has_dropouts = false;  // TODO: estimate from expected vs actual points
  summary.saturation = false;    // TODO: derive from intensity or known limits

  if (count > 0) {
    summary.mean_range = static_cast<float>(sum / static_cast<double>(count));
  } else {
    summary.min_range = 0.0f;
    summary.mean_range = 0.0f;
  }
}

}  // namespace lidar_preprocess

#include "rclcpp_components/register_node_macro.hpp"
RCLCPP_COMPONENTS_REGISTER_NODE(lidar_preprocess::VoxelizerNode)