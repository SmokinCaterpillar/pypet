__author__ = 'Robert Meyer'

import getopt
import sys
import os

from pypet.tests.hdf5_multiproc_test import MultiprocLockTest,MultiprocQueueTest,MultiprocSortLockTest,MultiprocSortQueueTest
from pypet.tests.parameter_test import ArrayParameterTest,PickleParameterTest,SparseParameterTest,ParameterTest, \
    ResultTest,SparseResultTest,PickleResultTest
from pypet.tests.trajectory_test import SingleRunQueueTest, SingleRunTest, TrajectoryFindTest, TrajectoryMergeTest, TrajectoryTest
from pypet.tests.hdf5_storage_test import ResultSortTest, EnvironmentTest, StorageTest
from pypet.tests.hdf5_merge_test import TestMergeResultsSort, MergeTest
from pypet.tests.hdf5_removal_and_continue_tests import ContinueTest
from pypet.tests.utilstest import CartesianTest
from pypet.tests.environment_test import EnvironmentTest
from pypet.tests.annotations_test import AnnotationsTest
from pypet.tests.test_helpers import make_run

# Works only if someone has installed Brian
try:
    from pypet.tests.briantests.brian_parameter_test import BrianParameterTest, BrianParameterStringModeTest, \
        BrianResult, BrianResultStringModeTest
    if not os.getenv('TRAVIS',False):
        from pypet.tests.briantests.brian_monitor_test import BrianMonitorTest
        from pypet.tests.briantests.brian_full_network_test import NetworkTest
except ImportError as e:
    print repr(e)
    pass


if __name__ == '__main__':
    opt_list, _ = getopt.getopt(sys.argv[1:],'k',['folder='])
    remove = None
    folder = None
    for opt, arg in opt_list:
        if opt == '-k':
            remove = False
            print 'I will keep all files.'

        if opt == '--folder':
            folder = arg
            print 'I will put all data into folder `%s`.' % folder

    sys.argv=[sys.argv[0]]
    make_run(remove, folder)