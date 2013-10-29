__author__ = 'Robert Meyer'

'''
Taken from http://blog.schettino72.net/posts/python-code-coverage-multiprocessing.html

Module enables code coverage for multiprocessing
'''

from multiprocessing import Process

def coverage_multiprocessing_process(): # pragma: no cover
    try:
        import coverage
    except:
        # give up monkey-patching if coverage not installed
        return

    from coverage.collector import Collector
    from coverage.control import coverage
    # detect if coverage was running in forked process
    if Collector._collectors:
        class Process_WithCoverage(Process):
            def _bootstrap(self):
                cov = coverage(data_suffix=True)
                cov.start()
                try:
                    return Process._bootstrap(self)
                finally:
                    cov.stop()
                    cov.save()
        return Process_WithCoverage

ProcessCoverage = coverage_multiprocessing_process()
if ProcessCoverage:
    print 'USING MP COVERAGE!'
    Process = ProcessCoverage