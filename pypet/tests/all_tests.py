__author__ = 'Robert Meyer'



import getopt
import sys
from hdf5_multiproc_test import MultiprocLockTest,MultiprocQueueTest,MultiprocSortLockTest,MultiprocSortQueueTest
from parameter_test import ArrayParameterTest,PickleParameterTest,SparseParameterTest,ParameterTest
from trajectory_test import SingleRunQueueTest, SingleRunTest, TrajectoryFindTest, TrajectoryMergeTest, TrajectoryTest
from hdf5_storage_test import ResultSortTest, EnvironmentTest
from hdf5_merge_test import TestMergeResultsSort, MergeTest
from hdf5_removal_and_continue_tests import ContinueTest
from utilstest import CartesianTest
from environment_test import EnvironmentTest
from test_helpers import make_run

import os
import unittest
# Works only if someone has installed Brian
try:
    from brian_parameter_test import BrianParameterTest, BrianParameterStringMode
    if not os.getenv('TRAVIS',False):
        from brian_full_network_test import NetworkTest
except ImportError:
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
            print 'I will put all data into folder >>%s<<' % folder

    make_run(remove, folder)