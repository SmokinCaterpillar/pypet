__author__ = 'Robert Meyer'


from distutils.core import setup

setup(
    name='pyPET',
    version='0.1.0',
    packages=['pypet',],
    license='BSD',
    author='Robert Meyer',
    author_email='robert.meyer@ni.tu-berlin.de',
    description='A toolkit for numerical simulations to allow easy parameter exploration and storage of results.',
    long_description=open('README.md').read(),
    install_requires=[
        "tables >= 3.0.0",
        "pandas >= 0.12.0",
    ],
)