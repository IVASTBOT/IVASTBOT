# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run

```bash
# Source ROS2 environment (required in every shell)
source /opt/ros/humble/setup.bash
source install/setup.bash   # after first build

# Build all packages
colcon build --symlink-install

# Build a single package
colcon build --symlink-install --packages-select kinco_canopen_hw

# Launch full robot
ros2 launch motor motor.launch.py

# Launch Flydigi gamepad controller
ros2 launch flydigi flydigi.launch.py

# Launch SLAM mapping (after bringup)
ros2 launch slam slam.launch.xml

# Visualize in RViz
ros2 launch motor rviz.launch.py
```

## Architecture

Differential-drive mobile robot with five packages:

### `kinco_canopen_hw` (C++17)
ros2_control `SystemInterface` plugin for Kinco servo motors. Uses **CANopen DS402** (Profile Velocity mode 3) over SLCAN adapter at `/dev/ttyACM0` (921600 baud, 500 kbps CAN).

- PDO-based communication: RPDO1 sends velocity command (`0x60FF`), TPDO1 receives actual velocity (`0x606C`) continuously
- DS402 state machine runs on `on_configure()`: shutdown → switch-on-disabled → ready-to-switch-on → switched-on → operation-enabled
- **Velocity conversion**: `int32_t = rad/s × velocity_factor / gear_ratio` where `velocity_factor=2731`, `gear_ratio=9`
- Motor CAN IDs: left=1, right=2
- Three independent low-pass filter chains: cmd (6 Hz), feedback (12 Hz), odometry (20 Hz)
- Zero hysteresis: enter idle at 0.02 rad/s, exit at 0.04 rad/s; skips PDO after 10 consecutive zero cycles to avoid bus spam
- TPDO timeout: 120 ms — if no feedback received, reports stale velocity
- Accel/decel profile: 1500/1800 raw units written to `0x6083`/`0x6084` on startup

### `motor` (Python — bringup package)
Main launch orchestration and robot URDF.

- `motor.launch.py` starts: robot_state_publisher → controller_manager → (2s delay) → joint_state_broadcaster + drivetrain_controller → hins_le_ros2_node → scan_filter_node
- `/cmd_vel` is remapped from `/drivetrain_controller/cmd_vel_unstamped`
- `controllers.yaml`: DiffDriveController at 100 Hz, wheel_separation=0.39 m, wheel_radius=0.081 m, max linear ±1.5 m/s, max angular ±2.2 rad/s

URDF TF tree: `map` → `odom` → `base_link` → `laser_frame` (x=0.4, z=0.125 from base_link), `base_footprint`, `imu_link`

### `hins_le_ros2` (C++14)
Driver for the **HINS Xingsong 2D LiDAR** over TCP. Connects to `192.168.10.52:8080`.

- Publishes `sensor_msgs/LaserScan` on `/scan` (frame: `laser_frame`)
- 360° FOV, up to 60 m range, 200 kHz measurement frequency, 20 RPM motor speed
- Shadow filter removes trailing artifacts (configurable angle window)
- Exposes a service `/HinsLESrv` (`hins_laser_interfaces/HinsSrv`) — request a channel, get back `area1/area2/area3` boolean zone status

### `hins_laser_interfaces` (CMake — interfaces only)
Custom ROS2 message and service definitions used by `hins_le_ros2`:
- `HinsMsg.msg`: `bool area1, area2, area3, success`
- `HinsSrv.srv`: request `int64 channel` → response `bool area1, area2, area3, success`

Must be built before `hins_le_ros2`.

### `flydigi` (Python)
Gamepad controller node (pygame). Identical in behavior to the ivastbot_ws version — see that repo's CLAUDE.md for details. Publishes `Twist` to `/cmd_vel` at 20 Hz with smooth ramping.

### `slam` (CMake — config only)
Wraps slam_toolbox. Subscribes to `/scan_filtered`. Switch between `mapping` and `localization` modes in `config/slam.yaml`.

## Key Device Paths

| Device | Default | Baud/Protocol |
|--------|---------|---------------|
| SLCAN adapter (CANopen→USB) | `/dev/ttyACM0` | 921600 baud, 500 kbps CAN |
| HINS LiDAR | `192.168.10.52:8080` | TCP |

## Key Topics

| Topic | Type | Source |
|-------|------|--------|
| `/scan` | LaserScan | hins_le_ros2 |
| `/scan_filtered` | LaserScan | scan_filter_node |
| `/cmd_vel` | Twist | flydigi / external |
| `/odom` | Odometry | drivetrain_controller |
| `/speed_setting` | Float64 | flydigi_node |
