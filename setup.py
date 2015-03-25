__author__ = 'Robert Meyer'

import re
import sys

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

install_requires=[
        'tables >= 2.3.1',
        'pandas >= 0.12.0',
        'numpy >= 1.6.1',
        'scipy >= 0.9.0']

# check if importlib exists, if not (aka python 2.6) install it
try:
    import importlib
except ImportError:
    install_requires.append('importlib')

if (sys.version_info < (2, 7, 0)):
    # For Python 2.6 we additionally need these packages:
    install_requires.append(['unittest2'])
    install_requires.append('ordereddict >= 1.1')
    install_requires.append('importlib >= 1.0.1')
    install_requires.append('logutils >= 0.3.3')

# For versioning, Version found in pypet._version.py
verstrline = open('pypet/_version.py', "rt").read()

VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
mo = re.search(VSRE, verstrline, re.M)
if mo:
    verstr = mo.group(1)
else:
    raise RuntimeError('Unable to find version in pypet/_version.py')

setup(
    name='pypet',
    version=verstr,
    packages=['pypet',
              'pypet.brian',
              'pypet.utils',
              'pypet.tests',
              'pypet.tests.unittests',
              'pypet.tests.integration',
              'pypet.tests.profiling',
              'pypet.tests.testutils',
              'pypet.tests.unittests.briantests',
              'pypet.tests.integration.briantests'],
    package_data={'pypet.tests': ['testdata/*.hdf5'], 'pypet': ['logging/*.ini']},
    license='BSD',
    author='Robert Meyer',
    author_email='robert.meyer@ni.tu-berlin.de',
    description='A toolkit for numerical simulations to allow easy parameter exploration and storage of results.',
    long_description=open('README.md').read(),
    url='https://github.com/SmokinCaterpillar/pypet',
    install_requires=install_requires,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Intended Audience :: Science/Research',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Topic :: Scientific/Engineering',
        'License :: OSI Approved :: BSD License',
        'Topic :: Utilities']
)