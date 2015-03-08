"""Module running all examples in the examples directory

Suppresses all openings of plots
"""
__author__ = 'Robert Meyer'

import glob
import os
import sys
import platform
import subprocess

try:
    import brian
except ImportError:
    print('No BRIAN module found, will skip the example')
    brian = None

system = platform.system()
print('*** Running under %s ***' % str(system))

to_skip = set()
if brian is None:
    to_skip.add('07')
    to_skip.add('11')
if system == 'Windows':
    # Appveyor is too slow for this example, so we skip it
    to_skip.add('13')

if len(to_skip) == 0:
    print ('----- I will run all tests -----')
else:
    print('----- I will skip the following tests: `%s` ----' % to_skip)

def skip(name):
    for item in to_skip:
        if item in name:
            return True
    return False

def prepend_mpl_import(filename):
    """Writes a new python file and prepends the a matplotlib import.

    This avoids opening the plots within the test suite
    """
    with open(filename, mode='r') as fh:
        file_text = fh.read()

    import_matplotlib = ('import matplotlib\n'
                        'matplotlib.use(\'Agg\')\n'
                        'print(\'IMPORTED MATPLOTLIB WITH AGG\')\n')
    new_filename = 'tmp_' + filename
    with open(new_filename, mode='w') as fh:
        fh.write(import_matplotlib)
        fh.write(file_text)

    return new_filename

def execute_example(filename):
    """Executes a file as script.

    Firs prepends matplotlib import

    """
    #filename = os.path.join(os.getcwd(), filename)
    new_filename = None
    try:
        new_filename = prepend_mpl_import(filename)
        retcode = subprocess.call(sys.executable + ' ' + new_filename, shell=True)
        if retcode != 0:
            print('### ERROR: Example `%s` failed! ###' % filename)
            sys.exit(retcode)
        else:
            print('#### Example successful ####')
    finally:
        if new_filename is not None:
            os.remove(new_filename)


def main():
    os.chdir(os.path.join('..','..','examples'))
    sys.path.append(os.getcwd())
    simple_examples = glob.glob('*.py')
    assert len(simple_examples) == 14 + 1

    for simple_example in simple_examples:
        if simple_example == '__init__':
            continue

        if skip(simple_example):
            print("---------- Skipping %s ----------" % simple_example)
        else:
            print("########## Running %s ###########" % simple_example)
            execute_example(simple_example)

    ex17 = 'example_17_wrapping_an_existing_project'
    if skip(ex17):
        print("------- Skipping %s -------" % ex17)
    else:
        os.chdir(ex17)
        sys.path.append(os.getcwd())
        print('Running original')
        execute_example('original.py')
        print('Running pypet wrapping')
        execute_example('pypetwrap.py')
        os.chdir('..')

    ex13 = 'example_13_post_processing'
    if skip(ex13):
        print("------- Skipping %s -------" % ex13)
    else:
        print("########## Running %s ###########" % ex13)
        os.chdir(ex13)
        sys.path.append(os.getcwd())
        print("Running main")
        execute_example('main.py')
        print("Running analysis")
        execute_example('analysis.py')
        print("Running pipeline")
        execute_example('pipeline.py')
        os.chdir('..')

    ex11 = 'example_11_large_scale_brian_simulation'
    if skip(ex11):
        print("------- Skipping %s -------" % ex11)
    else:
        print("########## Running %s ###########" % ex11)

        os.chdir(ex11)
        sys.path.append(os.getcwd())
        print("Running script")
        execute_example('runscript.py')
        print("Running analysis")
        execute_example('plotff.py')
        os.chdir('..')

if __name__ == '__main__':
    main()