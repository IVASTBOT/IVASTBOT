# Omini Robot URDF Package

This package contains URDF/Xacro files for the omini robot and launch files for visualization and simulation.

## File Structure

```
omini_urdf/
├── CMakeLists.txt
├── package.xml
├── launch/
│   ├── display_rviz.launch.py      # Launch RViz visualization
│   ├── gazebo_simulation.launch.py # Launch Gazebo simulation
│   ├── check_urdf.launch.py        # Launch both with arguments
│   └── urdf_config.rviz            # RViz configuration
└── urdf/
    ├── omni_robot.xacro
    ├── omni_robot_base.xacro
    └── utlis.xacro
```

## Usage

### 1. Build the package
```bash
cd ~/ros2_ws
source /opt/ros/foxy/setup.bash
colcon build --packages-select omini_urdf
source install/setup.bash
```

### 2. Check URDF in RViz
```bash
# Launch RViz with the robot model
ros2 launch omini_urdf display_rviz.launch.py

# Or use the combined launch file
ros2 launch omini_urdf check_urdf.launch.py use_rviz:=true
```

### 3. Check URDF in Gazebo
```bash
# Launch Gazebo simulation
ros2 launch omini_urdf gazebo_simulation.launch.py

# Or use the combined launch file
ros2 launch omini_urdf check_urdf.launch.py use_gazebo:=true

# Launch with custom position
ros2 launch omini_urdf gazebo_simulation.launch.py x_pos:=1.0 y_pos:=2.0 z_pos:=0.5
```

### 4. Launch both RViz and Gazebo
```bash
ros2 launch omini_urdf check_urdf.launch.py use_rviz:=true use_gazebo:=true
```

## Launch File Parameters

### display_rviz.launch.py
- `use_sim_time` (default: false): Use simulation time

### gazebo_simulation.launch.py
- `use_sim_time` (default: true): Use simulation time
- `world` (default: empty.world): World file to load
- `x_pos` (default: 0.0): Initial x position
- `y_pos` (default: 0.0): Initial y position  
- `z_pos` (default: 0.1): Initial z position

### check_urdf.launch.py
- `use_rviz` (default: false): Launch RViz
- `use_gazebo` (default: false): Launch Gazebo

## Troubleshooting

1. **URDF not displaying**: Check if the xacro files are properly formatted and all includes are correct
2. **Missing packages**: Install required dependencies:
   ```bash
   sudo apt install ros-foxy-robot-state-publisher ros-foxy-joint-state-publisher-gui ros-foxy-xacro ros-foxy-gazebo-ros-pkgs
   ```
3. **Gazebo not launching**: Make sure Gazebo is installed:
   ```bash
   sudo apt install gazebo11 ros-foxy-gazebo-ros
   ```

## Dependencies

- robot_state_publisher
- joint_state_publisher
- joint_state_publisher_gui
- rviz2
- xacro
- gazebo_ros
- gazebo_ros_pkgs
