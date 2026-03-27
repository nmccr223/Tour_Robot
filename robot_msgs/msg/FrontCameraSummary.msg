# Compact, low-latency summary produced by OAK-D processor nodes.
#
# This message intentionally avoids large payloads (images/point clouds) and
# captures only the key values needed by control and safety logic.

builtin_interfaces/Time stamp
string frame_id

# Obstacle statistics inside processor-defined FOV and range limits.
bool has_obstacle
float32 min_distance
float32 mean_distance

# Human-presence safety signals from NN detections.
bool person_detected
float32 person_min_distance

# Debug and observability counters for monitoring/telemetry.
uint32 num_points_used
uint32 num_detections
