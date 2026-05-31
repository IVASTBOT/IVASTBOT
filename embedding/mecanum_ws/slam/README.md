# SLAM Package

This package provides SLAM (Simultaneous Localization and Mapping) capabilities for the omni-directional robot using SLAM Toolbox.

## Purpose
- **Mapping Only**: This package is optimized for creating maps of the environment
- **Navigation**: Use the separate `navigation` package for autonomous navigation with created maps

## Files Structure
```
slam/
├── config/
│   ├── slam_mapping_params.yaml  # SLAM Toolbox parameters for mapping
│   └── slam.rviz                 # RViz configuration for SLAM visualization
├── launch/
│   ├── slam.launch.py            # Main SLAM launch file for mapping
│   └── rviz_slam.launch.py       # RViz visualization for SLAM
└── maps/                         # Generated maps are stored here
    ├── map_4_11.pgm
    └── map_4_11.yaml
```

## Usage

### 1. Start Robot Base
```bash
ros2 launch omni_controller omni_robot.launch.py
```

### 2. Start SLAM Mapping
```bash
ros2 launch slam slam.launch.py
```

### 3. Start SLAM Visualization (Optional)
```bash
ros2 launch slam rviz_slam.launch.py
```

### 4. Drive Robot to Create Map
Use your gamepad or teleop to drive the robot around the environment.

### 5. Save Map
```bash
ros2 run nav2_map_server map_saver_cli -f ~/map_name
```
example: 
```bash
ros2 run nav2_map_server map_saver_cli -f ~/ros2_ws_vanh/src/slam/maps/map_4_11
```
## Parameters
- `use_sim_time`: Set to 'true' when using simulation (default: 'false')
- `slam_params_file`: Path to custom SLAM parameters (default: uses package config)

## Output
- Generated maps are automatically saved in the `maps/` directory
- Maps can be used with the `navigation` package for autonomous navigation
