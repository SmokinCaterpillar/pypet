__author__ = 'Robert Meyer'

import getopt
import sys
import os

from pypet.tests.test_helpers import make_run

from pypet.tests.parameter_test import ArrayParameterTest,PickleParameterTest,SparseParameterTest,ParameterTest, \
    ResultTest,SparseResultTest,PickleResultTest
from pypet.tests.trajectory_test import SingleRunQueueTest, SingleRunTest, TrajectoryFindTest, TrajectoryMergeTest, TrajectoryTest
from pypet.tests.hdf5_storage_test import ResultSortTest, EnvironmentTest, StorageTest,\
    TestOtherHDF5Settings, TestOtherHDF5Settings2, FullStorageTest
from pypet.tests.hdf5_merge_test import TestMergeResultsSort, MergeTest
from pypet.tests.pipeline_test import TestPostProc
from pypet.tests.backwards_compat_test import LoadOldTrajectoryTest
try:
    from pypet.tests.hdf5_removal_and_continue_tests import ContinueTest
except ImportError as e:
    print('NO DILL TESTS!!!')
    print(repr(e)) # We end up here if `dill` is not installed
    pass
from pypet.tests.utilstest import CartesianTest, ProgressBarTest, TestNewTreeTranslation, \
    TestDictionaryMethods, TestEqualityOperations, TestFindUnique
from pypet.tests.environment_test import EnvironmentTest
from pypet.tests.annotations_test import AnnotationsTest
from pypet.tests.module_test import TestAllImport

from pypet.tests.link_test import LinkTrajectoryTests, LinkMergeTest, LinkEnvironmentTest

import pypet.utils.ptcompat as ptcompat

if ptcompat.tables_version == 3:
    from pypet.tests.shared_data_test import StorageDataTrajectoryTests, StorageDataEnvironmentTest

# Works only if someone has installed Brian
try:
    from pypet.tests.briantests.brian_parameter_test import BrianParameterTest, BrianParameterStringModeTest, \
        BrianResult, BrianResultStringModeTest
    from pypet.tests.briantests.brian_monitor_test import BrianMonitorTest
    from pypet.tests.briantests.brian_full_network_test import BrianFullNetworkTest
    from pypet.tests.briantests.module_test import TestAllBrianImport
except ImportError as e:
    print('NO BRIAN TESTS!!!')
    print(repr(e)) # We end up here if `brian` is not installed
    pass

if os.getenv('APPVEYOR', False):
    print('Running on APPVEYOR, will skip some tests for a faster build')
    # Skipping for speed, otherwise the built may run too long on the slow appveyor platform
    del TestOtherHDF5Settings2
    del TestOtherHDF5Settings

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