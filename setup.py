__author__ = 'Robert Meyer'

import re

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


verstr = "unknown"

try:
    verstrline = open('pypet/_version.py', "rt").read()
except EnvironmentError:
    pass # Okay, there is no version file.
else:
    VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
    mo = re.search(VSRE, verstrline, re.M)
    if mo:
        verstr = mo.group(1)
    else:
        print "unable to find version in %s" % (VERSIONFILE,)
        raise RuntimeError("if %s.py exists, it must be well-formed" % (VERSIONFILE,))


setup(
    name='pypet',
    version=verstr,
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