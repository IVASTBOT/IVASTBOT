# RViz HMI Plugins

This package provides RViz plugins for human-machine interface (HMI) visualization and control panels.

## Plugins

### Robot Status Panel
Visual monitoring and control interface for the robot control system.

**Features:**
- Real-time system status display
- Mode control buttons
- Emergency stop functionality
- System health indicators
- Performance metrics visualization

**Usage:**
1. Add "Robot Status Panel" from Panels menu in RViz
2. Configure display options
3. Monitor system status and control robot modes

## Package Structure

```
rviz_hmi_plugins/
├── CMakeLists.txt
├── package.xml
├── README.md
├── src/
│   ├── robot_status_panel.h          # Status panel header
│   ├── robot_status_panel.cpp        # Status panel implementation
│   └── ... (other existing panels)
├── plugin_description.xml            # Plugin definitions
└── config/
    └── ... (existing configurations)
```

## Installation

```bash
cd /home/roscube/iop_amr_ws
colcon build --packages-select rviz_hmi_plugins
source install/setup.bash
```

## Integration

This package integrates with the `robot_control_system` package for comprehensive robot control and monitoring.

- **Control System**: `robot_control_system` provides the backend logic
- **UI Panels**: `rviz_hmi_plugins` provides the visual interface
- **Coordination**: Both packages work together for complete functionality

## Development

See individual plugin source files for implementation details.
