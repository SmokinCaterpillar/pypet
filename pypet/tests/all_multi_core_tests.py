__author__ = 'Robert Meyer'

import getopt
import sys
import os

from pypet.tests.hdf5_multiproc_test import MultiprocLockTest,MultiprocQueueTest,MultiprocSortLockTest,MultiprocSortQueueTest, \
    MultiprocNoPoolLockTest,MultiprocNoPoolQueueTest,MultiprocNoPoolSortLockTest,MultiprocNoPoolSortQueueTest, CapTest

from pypet.tests.pipeline_test import TestMPPostProc, TestMPImmediatePostProc

try:
    from pypet.tests.hdf5_removal_and_continue_tests import ContinueMPTest, ContinueMPPoolTest
except ImportError as e:
    print(repr(e)) # We end up here if `dill` is not installed
    pass

from pypet.tests.test_helpers import make_run

# Works only if someone has installed Brian
try:
    from pypet.tests.briantests.brian_full_network_test import  BrianFullNetworkMPTest
except ImportError as e:
    print(repr(e))
    pass


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