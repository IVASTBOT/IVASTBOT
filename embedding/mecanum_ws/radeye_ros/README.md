# Dose Logger

A ROS2 node that subscribes to the `dose` topic and saves radiation dose data to a CSV file.

## Features

- Subscribes to the `dose` topic (std_msgs/Float64)
- Saves data with timestamps to CSV format
- Automatically creates directories if they don't exist
- Configurable output file path
- Can run independently or alongside the radeye sensor node

## Installation

Build the package:

```bash
cd ~/omni_ws
colcon build --packages-select radeye_ros
source install/setup.bash
```

## Usage

### Option 1: Run with launch file (Recommended)

```bash
# Use default path (<package>/radiation_logs/dose_data.csv)
ros2 launch radeye_ros dose_logger.launch.xml

# Specify custom file path
ros2 launch radeye_ros dose_logger.launch.xml file_path:=/home/ivastbot/my_data/radiation.csv

# Use relative path
ros2 launch radeye_ros dose_logger.launch.xml file_path:=./dose_data.csv
```

### Option 2: Run directly with ros2 run

```bash
# Use default path
ros2 run radeye_ros dose_logger

# Specify custom file path
ros2 run radeye_ros dose_logger --ros-args -p file_path:=/path/to/your/file.csv
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | string | `<package>/radiation_logs/dose_data.csv` | Full path to the CSV output file |

## Output Format

The logger saves data in CSV format with the following columns:

| Column | Description |
|--------|-------------|
| `timestamp` | Unix timestamp (seconds with decimal) |
| `datetime` | Human-readable datetime (YYYY-MM-DD HH:MM:SS.ffffff) |
| `dose_uSv_h` | Radiation dose in microsieverts per hour (µSv/h) |

Example output:

```csv
timestamp,datetime,dose_uSv_h
1700236845.123456,2025-11-17 15:30:45.123456,0.15
1700236846.234567,2025-11-17 15:30:46.234567,0.16
1700236847.345678,2025-11-17 15:30:47.345678,0.14
```

## Examples

### Example 1: Log to home directory

```bash
ros2 launch radeye_ros dose_logger.launch.xml file_path:=~/radiation_data.csv
```

### Example 2: Log to specific directory with date

```bash
ros2 launch radeye_ros dose_logger.launch.xml file_path:=/home/ivastbot/logs/dose_$(date +%Y%m%d_%H%M%S).csv
```

### Example 3: Check if logger is receiving data

```bash
# Terminal 1: Start the sensor (if not already running)
ros2 launch radeye_ros radeye.launch.xml

# Terminal 2: Start the logger
ros2 launch radeye_ros dose_logger.launch.xml

# Terminal 3: Monitor the topic
ros2 topic echo /dose

# Terminal 4: Check the log file
tail -f /home/ivastbot/ros2_ws_vanh/src/radeye_ros/radiation_logs/dose_data.csv

scp /home/ivastbot/ros2_ws_vanh/src/radeye_ros/radiation_logs/dose_data.csv iop@192.168.58.29:/home/iop
```

## Troubleshooting

### Logger not receiving data

1. Make sure the radeye sensor node is running:
   ```bash
   ros2 node list
   # Should show: /radeye_node
   ```

2. Check if the dose topic is publishing:
   ```bash
   ros2 topic list
   # Should show: /dose
   
   ros2 topic echo /dose
   # Should show dose values
   ```

3. Verify the logger node is running:
   ```bash
   ros2 node list
   # Should show: /dose_logger
   ```

### Permission denied error

Make sure the directory is writable:

```bash
chmod 755 /home/ivastbot/ros2_ws_vanh/src/radeye_ros/radiation_logs
```

### File not found

The logger automatically creates directories, but if you encounter issues:

```bash
mkdir -p /path/to/your/directory
```

## Notes

- The logger appends to existing files, so data won't be overwritten if you restart the node
- If the file doesn't exist, it will be created with headers automatically
- Use `~` for home directory paths (e.g., `~/logs/dose.csv`)
- Relative paths are relative to where you run the command
