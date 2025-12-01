# Summary of a single LD19 LaserScan, preprocessed on the CM5.

builtin_interfaces/Time stamp
string frame_id

# Global statistics over all valid ranges in the scan.
float32 min_distance           # Smallest valid range (meters), or 0 if none.
float32 mean_distance          # Mean of all valid ranges (meters), or 0 if none.
float32 max_distance           # Largest valid range (meters), or 0 if none.
uint32 num_readings            # Number of valid readings used in the stats.

# Sectorized view (optional but useful for control / UI).
# The scan is divided into num_sectors equal angular slices; each stores the
# minimum range in that sector (meters). If no valid reading exists for a
# sector, its entry is 0.
uint32 num_sectors
float32[] sector_min_distances
