from setuptools import setup, find_packages


setup(
    name='gearbox',
    version='0.0.1',
    description='PyGears visualization GUI',

    # The project's main homepage.
    url='https://github.com/bogdanvuk/gearbox',

    # Author details
    author='Bogdan Vukobratovic',
    author_email='bogdan.vukobratovic@gmail.com',

    # Choose your license
    license='MIT',

    python_requires='>=3.6.0',
    install_requires=['pygears', 'pexpect', 'PySide2', 'pygraphviz', 'pygments'],

    packages=find_packages(exclude=['examples*', 'docs']),
    package_data={'': ['*.json', '.spacemacs']},
    include_package_data=True,
)
