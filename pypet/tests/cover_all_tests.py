__author__ = 'Robert Meyer'

import multiprocessing as mp
import coverage

def coverage_multiprocessing_process(): # pragma: no cover
    """ Function to monkey patch mp Process for multiprocess code coverage.

    Taken from http://blog.schettino72.net/posts/python-code-coverage-multiprocessing.html

    """
    from coverage.collector import Collector
    from coverage.control import coverage
    # detect if coverage was running in forked process
    if Collector._collectors:
        class Process_WithCoverage(mp.Process):
            def _bootstrap(self):
                cov = coverage(data_suffix=True)
                cov.start()
                try:
                    return mp.Process._bootstrap(self)
                finally:
                    cov.stop()
                    cov.save()
        return Process_WithCoverage

ProcessCoverage = coverage_multiprocessing_process()
if ProcessCoverage:
    mp.Process = ProcessCoverage

from pypet.tests.all_single_core_tests import *

from pypet.tests.all_multi_core_tests import *


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
    make_run(remove, folder)