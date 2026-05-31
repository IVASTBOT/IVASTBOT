from setuptools import setup
import os
from glob import glob

package_name = 'omni_controller'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ivastbot',
    maintainer_email='ivastbot@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            "teleop_node = omni_controller.my_teleop:main",
            "bridge_node = omni_controller.stm32_usart:main",
            "gamepad_node = omni_controller.gamepad_omni:main",
            "odometry_node = omni_controller.odometry_node:main"
        ],
    },
)
