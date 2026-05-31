#!/bin/bash

# Source ROS environment
source /opt/ros/foxy/setup.bash
source /home/vanh/ros2_ws/install/setup.bash

echo "=== URDF Structure Analysis ==="
echo ""

# Convert xacro to urdf
echo "1. Converting Xacro to URDF..."
xacro /home/vanh/ros2_ws/src/omini_urdf/urdf/omni_robot.xacro > /tmp/robot.urdf

if [ $? -eq 0 ]; then
    echo "✓ Xacro conversion successful"
else
    echo "✗ Xacro conversion failed"
    exit 1
fi

echo ""
echo "2. Checking URDF validity..."
check_urdf /tmp/robot.urdf

echo ""
echo "3. Link Analysis:"
echo "Found links:"
grep -o '<link name="[^"]*"' /tmp/robot.urdf | cut -d'"' -f2 | sort

echo ""
echo "4. Joint Analysis:"
echo "Found joints:"
grep -o '<joint name="[^"]*"' /tmp/robot.urdf | cut -d'"' -f2 | sort

echo ""
echo "5. Wheel Joint Details:"
grep -A 5 -B 1 "wheel.*joint" /tmp/robot.urdf | grep -E "(joint name|parent link|child link|origin xyz)"

echo ""
echo "6. Material Analysis:"
echo "Materials used:"
grep -o '<material name="[^"]*"' /tmp/robot.urdf | cut -d'"' -f2 | sort | uniq

# Clean up
rm -f /tmp/robot.urdf
