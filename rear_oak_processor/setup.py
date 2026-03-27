from setuptools import setup

package_name = 'rear_oak_processor'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/rear_oak_processor.launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Tour Robot Team',
    maintainer_email='tour-robot@example.com',
    description='Rear OAK-D point cloud and detection post-processing for Tour Robot.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'rear_oak_node = rear_oak_processor.rear_oak_node:main',
        ],
    },
)
