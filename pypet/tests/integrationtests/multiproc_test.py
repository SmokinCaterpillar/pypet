__author__ = 'Robert Meyer'

import logging
import random
import os

from pypet import pypetconstants
from pypet.environment import Environment
from pypet.tests.integrationtests.environment_test import EnvironmentTest, ResultSortTest
from pypet.tests.testutils.ioutils import run_suite,make_temp_file, make_trajectory_name, \
    get_log_level
from pypet.tests.testutils.data import create_param_dict, add_params


class MultiprocQueueTest(EnvironmentTest):

    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'queue', 'pool'

    def set_mode(self):
        EnvironmentTest.set_mode(self)
        self.mode = pypetconstants.WRAP_MODE_QUEUE
        self.multiproc = True
        self.ncores = 4
        self.use_pool=True


class MultiprocLockTest(EnvironmentTest):

    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'lock', 'pool',

    # def test_run(self):
    #     super(MultiprocLockTest, self).test_run()

    def set_mode(self):
        EnvironmentTest.set_mode(self)
        self.mode = pypetconstants.WRAP_MODE_LOCK
        self.multiproc = True
        self.ncores = 4
        self.use_pool=True

class MultiprocSortQueueTest(ResultSortTest):

    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'queue', 'pool',

    def set_mode(self):
        self.mode = pypetconstants.WRAP_MODE_QUEUE
        self.multiproc = True
        self.ncores = 3
        self.use_pool=True


class MultiprocSortLockTest(ResultSortTest):

    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'lock', 'pool',

    def set_mode(self):
        self.mode = pypetconstants.WRAP_MODE_LOCK
        self.multiproc = True
        self.ncores = 4
        self.use_pool=True


class MultiprocNoPoolQueueTest(EnvironmentTest):

    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'queue', 'nopool',

    def set_mode(self):
        EnvironmentTest.set_mode(self)
        self.mode = pypetconstants.WRAP_MODE_QUEUE
        self.multiproc = True
        self.ncores = 3
        self.use_pool=False


class MultiprocNoPoolLockTest(EnvironmentTest):

    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'lock', 'nopool',

    def set_mode(self):
        EnvironmentTest.set_mode(self)
        self.mode = pypetconstants.WRAP_MODE_LOCK
        self.multiproc = True
        self.ncores = 2
        self.use_pool=False


class MultiprocNoPoolSortQueueTest(ResultSortTest):

    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'queue', 'nopool',

    def set_mode(self):
        ResultSortTest.set_mode()
        self.mode = pypetconstants.WRAP_MODE_QUEUE
        self.multiproc = True
        self.ncores = 3
        self.use_pool=False


class MultiprocNoPoolSortLockTest(ResultSortTest):

    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'lock', 'nopool',

    def set_mode(self):
        ResultSortTest.set_mode()
        self.mode = pypetconstants.WRAP_MODE_LOCK
        self.multiproc = True
        self.ncores = 3
        self.use_pool=False


class CapTest(EnvironmentTest):

    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'lock', 'nopool', 'cap'

    def setUp(self):

        self.multiproc = True
        self.mode = 'LOCK'

        self.trajname = make_trajectory_name(self)

        self.filename = make_temp_file(os.path.join('experiments',
                                                    'tests',
                                                    'HDF5',
                                                    '%s.hdf5' % self.trajname))
        self.logfolder = make_temp_file(os.path.join('experiments','tests','Log'))

        random.seed()


        env = Environment(trajectory=self.trajname,filename=self.filename,
                          file_title=self.trajname, log_folder=self.logfolder,
                          log_levels=get_log_level(), log_stdout=False,
                          results_per_run=5,
                          derived_parameters_per_run=5,
                          multiproc=True,
                          ncores=3,
                          cpu_cap=0.001, # Ensure that these are triggered
                          memory_cap=0.001,
                          swap_cap=0.001,
                          use_pool=False)

        traj = env.v_trajectory

        ## Create some parameters
        self.param_dict={}
        create_param_dict(self.param_dict)
        ### Add some parameter:
        add_params(traj,self.param_dict)

        #remember the trajectory and the environment
        self.traj = traj
        self.env = env




if __name__ == '__main__':
    run_suite()