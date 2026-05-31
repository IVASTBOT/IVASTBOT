#!/bin/bash

# Source ROS environment
source /opt/ros/foxy/setup.bash
source /home/vanh/ros2_ws/install/setup.bash

echo "Checking URDF file validity..."

# Convert xacro to urdf and check for errors
xacro /home/vanh/ros2_ws/src/omini_urdf/urdf/omni_robot.xacro > /tmp/robot.urdf

if [ $? -eq 0 ]; then
    echo "✓ Xacro conversion successful"
    
    # Check URDF validity
    check_urdf /tmp/robot.urdf
    
    if [ $? -eq 0 ]; then
        echo "✓ URDF file is valid"
        echo "Robot links found:"
        grep -o '<link name="[^"]*"' /tmp/robot.urdf | cut -d'"' -f2
    else
        echo "✗ URDF validation failed"
    fi
else
    echo "✗ Xacro conversion failed"
fi

# Clean up
rm -f /tmp/robot.urdf
