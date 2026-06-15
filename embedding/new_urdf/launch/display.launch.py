import os
import launch
import launch.conditions
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    urdf_file = os.path.join(pkg_share, 'urdf', 'urdf4.urdf')
    rviz_config = os.path.join(pkg_share, 'config', 'urdf4.rviz')

    use_gui = LaunchConfiguration('use_gui')

    with open(urdf_file, 'r') as f:
        robot_desc = f.read()

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_desc, 'use_sim_time': False}],
    )

    joint_state_publisher_gui = Node(
        package='joint_state_publisher_gui',
        executable='joint_state_publisher_gui',
        output='screen',
        condition=launch.conditions.IfCondition(use_gui),
    )

    joint_state_publisher = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        output='screen',
        condition=launch.conditions.UnlessCondition(use_gui),
    )

    rviz_args = ['-d', rviz_config] if os.path.exists(rviz_config) else []
    rviz2 = Node(
        package='rviz2',
        executable='rviz2',
        output='screen',
        arguments=rviz_args,
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_gui',
            default_value='true',
            description='Launch joint_state_publisher_gui instead of joint_state_publisher',
        ),
        robot_state_publisher,
        joint_state_publisher_gui,
        joint_state_publisher,
        rviz2,
    ])
