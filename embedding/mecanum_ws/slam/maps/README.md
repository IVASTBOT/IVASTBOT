# Maps Directory

This directory contains saved maps from SLAM operations.

- `.posegraph` files: SLAM Toolbox pose graph files for localization
- `.pgm` files: Occupancy grid map images
- `.yaml` files: Map metadata files

ros2 run nav2_map_server map_saver_cli -f ~/ros2_ws_vanh/src/slam/maps/map_4_11

## Usage

Maps are automatically saved here when using the SLAM Toolbox save functionality.
To use a saved map for localization, specify the map file path in the launch arguments.
