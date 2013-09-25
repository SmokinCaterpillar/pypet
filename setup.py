__author__ = 'Robert Meyer'


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup




setup(
    name='pypet',
    version='0.1a.1',
    packages=['pypet',
              'pypet.brian',
              'pypet.tests',
              'pypet.utils'],
    license='BSD',
    author='Robert Meyer',
    author_email='robert.meyer@ni.tu-berlin.de',
    description='A toolkit for numerical simulations to allow easy parameter exploration and storage of results.',
    long_description=open('long_description.txt').read(),
    url='http://pypi.python.org/pypi/pypet/',
    install_requires=[
        'tables >= 3.0.0',
        'pandas >= 0.12.0',
        'numpy >= 1.5.0'
    ],
)