from setuptools import setup

package_name = 'scan_filter'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='duyroscube',
    maintainer_email='duyroscube@todo.todo',
    description='Laser scan filter to remove self-scan from robot body',
    license='MIT',
    entry_points={
        'console_scripts': [
            'scan_filter_node = scan_filter.scan_filter_node:main',
        ],
    },
)
