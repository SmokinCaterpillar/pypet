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
                    omit='*/pypet/tests/*,*/shareddata.py'.split(','))

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

pypetpath=os.path.abspath(os.getcwd())
sys.path.append(pypetpath)
print('Appended path `%s`' % pypetpath)

from pypet.tests.testutils.ioutils import run_suite, discover_tests, TEST_IMPORT_ERROR, parse_args


if __name__ == '__main__':
    opt_dict = parse_args()
    tests_include = set(('TestMPImmediatePostProcLock',
                    'MultiprocFrozenPoolSortQueueTest',
                    'MultiprocFrozenPoolSortPipeTest',
                    'MultiprocLinkNoPoolLockTest',
                    'MultiprocLinkNoPoolQueueTest',
                    'MultiprocLinkQueueTest',
                    'MultiprocPoolSortLocalTest',
                    'MultiprocSCOOPSortLocalTest',
                    'MultiprocFrozenSCOOPSortNetlockTest',
                    'MultiprocFrozenSCOOPSortNetqueueTest',
                    'Brain2NetworkTest',
                    'BrainNetworkTest',
                    'CapTest'))
    pred = lambda class_name, test_name, tags: (class_name in tests_include or
                                                 'multiproc' not in tags)
    suite = discover_tests(pred)
    run_suite(suite=suite, **opt_dict)