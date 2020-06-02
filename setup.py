__author__ = 'Robert Meyer'

import re
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
try:
    # Used to convert md to rst for pypi, otherwise not needed
    import m2r
except ImportError:
    m2r = None

install_requires=[
    'tables',
    'pandas',
    'numpy',
    'scipy'
]

# For versioning, Version found in pypet._version.py
verstrline = open('pypet/_version.py', "rt").read()

VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
mo = re.search(VSRE, verstrline, re.M)
if mo:
    verstr = mo.group(1)
else:
    raise RuntimeError('Unable to find version in pypet/_version.py')

description = ('A toolkit for numerical simulations to allow '
               'easy parameter exploration and storage of results.')
if m2r is None:
    long_description = description
else:
    # convert markdown to rst
    long_description = m2r.convert(open('README.md').read())

setup(
    name='pypet',
    version=verstr,
    packages=['pypet',
              'pypet.brian2',
              'pypet.utils',
              'pypet.tests',
              'pypet.tests.unittests',
              'pypet.tests.integration',
              'pypet.tests.profiling',
              'pypet.tests.testutils',
              'pypet.tests.unittests.brian2tests',
              'pypet.tests.integration.brian2tests',
              ],
    package_data={'pypet.tests': ['testdata/*.hdf5'], 'pypet': ['logging/*.ini']},
    license='BSD',
    author='Robert Meyer',
    author_email='robert.meyer@alcemy.tech',
    description=description,
    long_description=long_description,
    url='https://github.com/SmokinCaterpillar/pypet',
    install_requires=install_requires,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Intended Audience :: Science/Research',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Topic :: Scientific/Engineering',
        'License :: OSI Approved :: BSD License',
        'Topic :: Utilities'],
    python_requires='>=3.6',
)