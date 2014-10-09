"""Module running all examples in the examples directory

Suppresses all openings of plots
"""
__author__ = 'Robert Meyer'

import matplotlib
matplotlib.use('Agg')

import glob
import os
import sys


os.chdir('../../examples')
sys.path.append(os.getcwd())
simple_examples = glob.glob('*.py')

assert len(simple_examples) == 11 + 1

for simple_example in simple_examples:
    if simple_example == '__init__':
        continue

    filename = os.path.join(os.getcwd(), simple_example)
    print "########## Running %s ###########" % simple_example
    execfile(filename, globals(), locals())


ex13 = 'example_13_post_processing'
print "########## Running %s ###########" % ex13
os.chdir(ex13)
sys.path.append(os.getcwd())
print "Running main"
filename = os.path.join(os.getcwd(), 'main.py')
execfile(filename)
print "Running analysis"
filename = os.path.join(os.getcwd(), 'analysis.py')
execfile(filename)
print "Running pipeline"
filename = os.path.join(os.getcwd(), 'pipeline.py')
execfile(filename)

ex11 = 'example_11_large_scale_brian_simulation'
print "########## Running %s ###########" % ex11
os.chdir('..')
os.chdir(ex11)
sys.path.append(os.getcwd())
print "Running script"
filename = os.path.join(os.getcwd(), 'runscript.py')
execfile(filename)
print "Running analysis"
filename = os.path.join(os.getcwd(), 'plotff.py')
execfile(filename)