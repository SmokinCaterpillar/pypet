__author__ = 'Robert Meyer'

import getopt
import sys
import os

from pypet.tests.test_helpers import make_run, combined_suites, combine_test_classes

from pypet.tests.hdf5_multiproc_test import MultiprocLockTest,MultiprocQueueTest,MultiprocSortLockTest,MultiprocSortQueueTest, \
    MultiprocNoPoolLockTest,MultiprocNoPoolQueueTest,MultiprocNoPoolSortLockTest,MultiprocNoPoolSortQueueTest, CapTest

from pypet.tests.link_multiproc_test import MultiprocLinkLockTest, MultiprocLinkNoPoolLockTest, MultiprocLinkNoPoolQueueTest, MultiprocLinkQueueTest

from pypet.tests.pipeline_test import TestMPPostProc, TestMPImmediatePostProc

ContinueMPTest = None
ContinueMPPoolTest = None
try:
    from pypet.tests.hdf5_removal_and_continue_tests import ContinueMPTest, ContinueMPPoolTest
except ImportError as e:
    print('NO DILL TESTS!!!')
    print(repr(e)) # We end up here if `dill` is not installed
    pass

# Works only if someone has installed Brian
BrianFullNetworkMPTest = None
try:
    from pypet.tests.briantests.brian_full_network_test import  BrianFullNetworkMPTest
except ImportError as e:
    print('NO BRIAN NETWORK TESTS!!!')
    print(repr(e))
    pass

extend_suite = combine_test_classes(ContinueMPTest,
                                    ContinueMPPoolTest,
                                    BrianFullNetworkMPTest)

no_pool_suite = combine_test_classes(MultiprocNoPoolLockTest,
                                 MultiprocNoPoolQueueTest)

env_suite = combine_test_classes(MultiprocLockTest,
                                 MultiprocQueueTest,
                                 CapTest)

sort_suite = combine_test_classes(MultiprocSortLockTest,
                                  MultiprocSortQueueTest,
                                  MultiprocNoPoolSortLockTest,
                                  MultiprocNoPoolSortQueueTest)

link_post_suite = combine_test_classes(MultiprocLinkLockTest,
                                       MultiprocLinkNoPoolLockTest,
                                       MultiprocLinkNoPoolQueueTest,
                                       MultiprocLinkQueueTest,
                                       TestMPPostProc,
                                       TestMPImmediatePostProc)


big_suite_1 = no_pool_suite
big_suite_2 = env_suite
big_suite_3 = combined_suites(sort_suite, link_post_suite, extend_suite)

suite_dict = {'1': big_suite_1, '2': big_suite_2, '3': big_suite_3}


if __name__ == '__main__':
    opt_list, _ = getopt.getopt(sys.argv[1:],'k',['folder=', 'suite='])
    remove = None
    folder = None
    suite = None

    for opt, arg in opt_list:
        if opt == '-k':
            remove = False
            print('I will keep all files.')

        if opt == '--folder':
            folder = arg
            print('I will put all data into folder `%s`.' % folder)

        if opt == '--suite':
            suite_no = arg
            print('I will run suite `%s`.' % suite_no)
            suite = suite_dict[suite_no]


    sys.argv=[sys.argv[0]]
    make_run(remove, folder, suite)