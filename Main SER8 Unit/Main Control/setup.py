from setuptools import setup
import os
from glob import glob

package_name = 'main_control'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob(os.path.join('..', 'Launcher', '*.launch.py'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Tour Robot Team',
    maintainer_email='tour-robot@example.com',
    description='Tour Robot Main Control - Navigation POC and System Management',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'navigation_poc = main_control.ser8_navigation_poc:main',
            'main_controller_node = main_control.main_controller_node:main',
            'shutdown_manager_node = main_control.shutdown_manager_node:main',
            'test_scan_publisher = main_control.test_scan_publisher:main',
            'plc_motor_test = main_control.plc_motor_client:main',
        ],
    },
)
