# IOP Robot (IVASTBOT)

This repository contains the software for the IOP (Institute of Physics) mobile robot platform used by the IOP Institute of Physics. It includes ROS2 packages, drivers, and bringup launch files needed to run the robot on a laptop or development machine.

## Contents
- `BR_AI/` — AI and application code
- `embedding/` — embedded workspaces (sensors, drivers, SDKs)
- `motor/`, `slam/`, `flydigi/` — robot bringup and controller packages

## Requirements
- Ubuntu 22.04 (recommended) or compatible Linux
- ROS 2 Humble
- Python 3.10+ for Python packages
- Build tools: `colcon`, `cmake`, `gcc`

## How to download
Clone the repository and switch to the `beta` branch (contains full workspace snapshot):

```bash
git clone https://github.com/IVASTBOT/IVASTBOT.git iop-robot
cd iop-robot
git checkout beta
```

If you only need core packages (smaller download), clone the repo and remove large SDKs or use a shallow clone:

```bash
git clone --depth 1 https://github.com/IVASTBOT/IVASTBOT.git iop-robot
cd iop-robot
```

## Setup on your laptop
1. Source ROS2 Humble (adjust if installed elsewhere):

```bash
source /opt/ros/humble/setup.bash
```

2. Install Python dependencies (inside a virtualenv is recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Build workspace with `colcon`:

```bash
# from repository root
colcon build --symlink-install
source install/setup.bash
```

4. Run the full bringup (example):

```bash
# Launch the robot bringup (this starts controllers, publishers, and nodes)
ros2 launch motor motor.launch.py
```

5. Optional: run Flydigi gamepad controller locally (example):

```bash
ros2 launch flydigi flydigi.launch.py
```

## Key commands
- Build: `colcon build --symlink-install`
- Source workspace: `source install/setup.bash`
- Launch bringup: `ros2 launch motor motor.launch.py`
- List ROS topics: `ros2 topic list`
- View nodes: `ros2 node list`

## Notes and troubleshooting
- The `embedding/` folder contains large SDKs and drivers; if you encounter large download or build times, remove or ignore specific SDK folders and only build required packages.
- If a package fails to build, inspect the package CMakeLists and ensure system dependencies are installed (`sudo apt install <deps>`).
- For CAN/serial devices, ensure appropriate permissions or run with `sudo` when necessary.

If you want, I can add a short script `scripts/setup.sh` to automate setup steps — tell me if you want that.

