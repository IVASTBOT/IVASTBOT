#!/usr/bin/env python3

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, Command, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    # Get the package directory
    pkg_share = FindPackageShare(package='omini_urdf').find('omini_urdf')
    
    # Path to the URDF file
    urdf_file = PathJoinSubstitution([pkg_share, 'urdf', 'omni_robot.xacro'])
    
    # Declare launch arguments
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation time if true'
    )
    
    world_arg = DeclareLaunchArgument(
        'world',
        default_value='',
        description='World file to load in Gazebo (leave empty for default empty world)'
    )
    
    x_pos_arg = DeclareLaunchArgument(
        'x_pos',
        default_value='0.0',
        description='Initial x position of the robot'
    )
    
    y_pos_arg = DeclareLaunchArgument(
        'y_pos',
        default_value='0.0',
        description='Initial y position of the robot'
    )
    
    z_pos_arg = DeclareLaunchArgument(
        'z_pos',
        default_value='0.1',
        description='Initial z position of the robot'
    )
    
    # Robot state publisher node
    robot_state_publisher_node = Node(
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
    )
    
    # Joint state publisher node (for robots with joints)
    joint_state_publisher_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        output='screen',
        parameters=[{'use_sim_time': LaunchConfiguration('use_sim_time')}]
    )
    
    # Gazebo launch
    gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare('gazebo_ros'),
                'launch',
                'gazebo.launch.py'
            ])
        ]),
        launch_arguments={
            'verbose': 'true',
            'pause': 'false'
        }.items()
    )
    
    # Spawn robot in Gazebo
    spawn_robot_node = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        name='spawn_entity',
        output='screen',
        arguments=[
            '-topic', 'robot_description',
            '-entity', 'omni_robot',
            '-x', LaunchConfiguration('x_pos'),
            '-y', LaunchConfiguration('y_pos'),
            '-z', LaunchConfiguration('z_pos')
        ]
    )
    
    return LaunchDescription([
        use_sim_time_arg,
        world_arg,
        x_pos_arg,
        y_pos_arg,
        z_pos_arg,
        gazebo_launch,
        robot_state_publisher_node,
        joint_state_publisher_node,
        spawn_robot_node
    ])
