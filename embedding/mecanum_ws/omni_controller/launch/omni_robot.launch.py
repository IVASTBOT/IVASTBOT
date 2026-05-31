#!/usr/bin/env python3

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource, AnyLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, Command, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue

def generate_launch_description():
    # Get the package directory for URDF
    pkg_share = FindPackageShare(package='mecanum_mr').find('mecanum_mr')
    
    # Path to the URDF file
    urdf_file = PathJoinSubstitution([pkg_share, 'urdf', 'mecanum_mr.xacro'])
    
    # Path to RPLidar launch file
    rplidar_launch = PathJoinSubstitution([
        FindPackageShare('omini_urdf'),
        'launch',
        'rplidar.launch.py'
    ])
    
    # Path to Radeye launch file
    radeye_launch = PathJoinSubstitution([
        FindPackageShare('radeye_ros'),
        'launch',
        'radeye.launch.xml'
    ])
    
    # Path to Orbbec Camera launch file
    camera_launch = PathJoinSubstitution([
        FindPackageShare('orbbec_camera'),
        'launch',
        'astra_pro_plus.launch.py'
    ])
    
    # Declare launch arguments
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation time if true'
    )
        
    frame_id_arg = DeclareLaunchArgument(
        'frame_id',
        default_value='lidar_link',
        description='Frame ID for RPLidar'
    )

    # RPLidar port arguments
    serial_port_arg = DeclareLaunchArgument(
        'serial_port',
        default_value='/dev/ttyUSB0',
        description='Serial port for RPLidar'
    )   

    # STM32 UART port argument
    stm32_port_arg = DeclareLaunchArgument(
        'stm32_port',
        default_value='/dev/tty1',
        description='Serial port for STM32 communication'
    )

    # Radeye port argument
    radeye_port_arg = DeclareLaunchArgument(
        'radeye_port',
        default_value='/dev/ttyRadeye',
        description='Serial port for Radeye radiation sensor'
    )
    
    # Enable camera argument
    enable_camera_arg = DeclareLaunchArgument(
        'enable_camera',
        default_value='false',
        description='Enable Orbbec camera if true'
    )
    
    # Camera name argument
    camera_name_arg = DeclareLaunchArgument(
        'camera_name',
        default_value='camera',
        description='Name for the camera'
    )
    
    return LaunchDescription([
        use_sim_time_arg,
        serial_port_arg,
        frame_id_arg,
        stm32_port_arg,
        radeye_port_arg,
        enable_camera_arg,
        camera_name_arg,
        
        # Robot Model Components
        # Robot state publisher node
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{
                'robot_description': ParameterValue(
                    Command(['xacro ', urdf_file]),
                    value_type=str
                ),
                'use_sim_time': LaunchConfiguration('use_sim_time')
            }]
        ),
        
        # Joint state publisher node (for publishing joint states)
        Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            name='joint_state_publisher',
            output='screen',
            parameters=[{
                'use_sim_time': LaunchConfiguration('use_sim_time')
            }]
        ),
        
        # STM32 UART Bridge Node
        Node(
            package='omni_controller',
            executable='bridge_node',
            name='stm32_bridge',
            output='screen',
            parameters=[{
                'port': LaunchConfiguration('stm32_port')
            }]
        ),
        
        # Odometry Node
        Node(
            package='omni_controller',
            executable='odometry_node', 
            name='odometry_calculator',
            output='screen',
            parameters=[]
        ),
        
        # RPLidar Launch
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(rplidar_launch),
            launch_arguments={
                'serial_port': LaunchConfiguration('serial_port'),
                'frame_id': LaunchConfiguration('frame_id'),
                'channel_type': 'serial',
                'serial_baudrate': '115200',
                'inverted': 'false',
                'angle_compensate': 'true',
                'scan_mode': 'Sensitivity'
            }.items()
        ),
        
        # Radeye Launch
        IncludeLaunchDescription(
            AnyLaunchDescriptionSource(radeye_launch),
            launch_arguments={
                'port': LaunchConfiguration('radeye_port')
            }.items()
        ),
        
        # Orbbec Camera Launch (conditional)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(camera_launch),
            launch_arguments={
                'camera_name': LaunchConfiguration('camera_name'),
                'enable_point_cloud': 'true',
                'enable_colored_point_cloud': 'false',
            }.items(),
            condition=IfCondition(LaunchConfiguration('enable_camera'))
        ),
    ])
