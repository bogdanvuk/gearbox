from setuptools import setup, find_packages

setup(
    name='pygears-gearbox',
    version='0.0.1rc5',
    description='PyGears visualization GUI',

    # The project's main homepage.
    url='https://github.com/bogdanvuk/gearbox',

    # Author details
    author='Bogdan Vukobratovic',
    author_email='bogdan.vukobratovic@gmail.com',

    # Choose your license
    license='MIT',
    python_requires='>=3.6.0',
    install_requires=[
        'pygears', 'pexpect', 'PySide2!=5.12.1', 'pygraphviz', 'pygments', 'python-xlib'
    ],
    packages=find_packages(exclude=['docs']),
    package_data={'': ['*.css', '*.png', '*.tcl', 'gtkwaverc']},
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'gearbox = gearbox.main:main',
        ],
    },
)
