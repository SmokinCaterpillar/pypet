__author__ = 'Robert Meyer'

import multiprocessing
# Monkey Patch from here: https://bitbucket.org/ned/coveragepy/issue/117/enable-coverage-measurement-of-code-run-by
def coverage_multiprocessing_process(): # pragma: no cover
    try:
        import coverage as _coverage
        _coverage
    except:
        return

    from coverage.collector import Collector
    from coverage import coverage
    # detect if coverage was running in forked process
    if Collector._collectors:
        original = multiprocessing.Process._bootstrap
        class Process_WithCoverage(multiprocessing.Process):
            def _bootstrap(self):
                cov = coverage(data_suffix=True,
                    omit='*/network.py,*/compat.py,*/ptcompat.py,*/pypet/tests/*,*/shareddata.py'.split(','))

                cov.start()
                try:
                    return original(self)
                finally:
                    cov.stop()
                    cov.save()
        return Process_WithCoverage

ProcessCoverage = coverage_multiprocessing_process()
if ProcessCoverage:
    multiprocessing.Process = ProcessCoverage
    print('Added Monkey-Patch for multiprocessing and code-coverage')


import sys
import os
import getopt
pypetpath=os.path.abspath(os.getcwd())
sys.path.append(pypetpath)
print('Appended path `%s`' % pypetpath)

from pypet.tests.testutils.ioutils import run_tests, discover_tests, TEST_IMPORT_ERROR

if __name__ == '__main__':
    opt_list, _ = getopt.getopt(sys.argv[1:],'k',['folder='])
    remove = None
    folder = None
    for opt, arg in opt_list:
        if opt == '-k':
            remove = False
            print('I will keep all files.')

        if opt == '--folder':
            folder = arg
            print('I will put all data into folder `%s`.' % folder)

    sys.argv=[sys.argv[0]]
    tests_include = set(('TestMPImmediatePostProc',
                    'MultiprocLinkNoPoolLockTest', 'MultiprocLinkNoPoolQueueTest',
                    'MultiprocLinkQueueTest', 'CapTest'))
    pred = lambda class_name, test_name, tags: (class_name in tests_include or
                                                 'multiproc' not in tags)
    suite = discover_tests(pred)
    run_tests(remove, folder, suite)