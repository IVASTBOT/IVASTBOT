# Omni Robot Controller with Odometry

This package provides control and odometry calculation for a 4-wheel omni robot.

## Nodes

### 1. STM32 Bridge Node (`bridge_node`)
- Reads encoder data from STM32 via UART
- Publishes raw encoder RPM data to `/serial_data`
- Publishes wheel velocities in m/s to `/vel_enc`
- Subscribes to `/cmd_vel` for robot control commands

### 2. Odometry Node (`odometry_node`)
- Subscribes to wheel velocities from `/vel_enc`
- Calculates robot odometry using forward kinematics
- Publishes odometry to `/odom` topic
- Broadcasts TF transform from `odom` to `base_link`

## Robot Configuration

### Physical Parameters (adjust in odometry_node.py):
- `wheel_radius`: 0.07m (wheel radius)
- `wheel_base_x`: 0.2m (distance from center to front/back wheels)  
- `wheel_base_y`: 0.2m (distance from center to left/right wheels)

### Wheel Configuration
The code assumes the following wheel order in the velocity array:
- Index 0: Front Left wheel
- Index 1: Front Right wheel  
- Index 2: Rear Left wheel
- Index 3: Rear Right wheel

## Usage

### Build the package:
```bash
cd ~/ros2_ws
colcon build --packages-select omni_controller
source install/setup.bash
```

### Run individual nodes:
```bash
# Start STM32 bridge node
ros2 run omni_controller bridge_node

# Start odometry node (in another terminal)
ros2 run omni_controller odometry_node
```

### Run both nodes with launch file:
```bash
ros2 launch omni_controller omni_robot.launch.py
```

### Send velocity commands:
```bash
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.2, y: 0.1, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.5}}"
```

### Monitor topics:
```bash
# View raw encoder data
ros2 topic echo /serial_data

# View wheel velocities  
ros2 topic echo /vel_enc

# View odometry
ros2 topic echo /odom

# View TF tree
ros2 run tf2_tools view_frames.py
```

## Kinematics

The odometry calculation uses forward kinematics for a 4-wheel omni robot:

```
vx = (v_fl + v_fr + v_rl + v_rr) / 4
vy = (-v_fl + v_fr + v_rl - v_rr) / 4  
vth = (-v_fl + v_fr - v_rl + v_rr) / (4 * (wheel_base_x + wheel_base_y))
```

Where:
- `vx`: Linear velocity in x direction (forward/backward)
- `vy`: Linear velocity in y direction (left/right)  
- `vth`: Angular velocity (rotation)
- `v_xx`: Individual wheel velocities

## Troubleshooting

1. **No odometry data**: Check that wheel velocities are being published to `/vel_enc`
2. **Incorrect movement**: Verify wheel order and adjust wheel_base parameters
3. **UART connection issues**: Check `/dev/ttyUSB0` port and baud rate (9600)
4. **TF errors**: Ensure both nodes are running and publishing at proper rates

## Customization

To adapt for your specific robot:
1. Adjust wheel radius and wheelbase parameters in `odometry_node.py`
2. Modify kinematic equations if your wheel configuration differs
3. Tune covariance matrices based on your robot's accuracy
4. Adjust publishing rates if needed (default: 50Hz for odometry)
