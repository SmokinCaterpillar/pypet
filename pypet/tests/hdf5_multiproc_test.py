__author__ = 'Robert Meyer'

import logging

from pypet import pypetconstants
from pypet.environment import Environment
from pypet.tests.hdf5_storage_test import EnvironmentTest, ResultSortTest

from pypet.tests.test_helpers import add_params, create_param_dict, simple_calculations, make_run,\
    make_temp_file, TrajectoryComparator, multiply, make_trajectory_name
from pypet.utils.explore import cartesian_product

import random
import os
import numpy as np
import scipy.sparse as spsp


class MultiprocQueueTest(EnvironmentTest):

    def set_mode(self):
        EnvironmentTest.set_mode(self)
        self.mode = pypetconstants.WRAP_MODE_QUEUE
        self.multiproc = True
        self.ncores = 4
        self.use_pool=True


class MultiprocLockTest(EnvironmentTest):

    # def test_run(self):
    #     super(MultiprocLockTest, self).test_run()

    def set_mode(self):
        EnvironmentTest.set_mode(self)
        self.mode = pypetconstants.WRAP_MODE_LOCK
        self.multiproc = True
        self.ncores = 4
        self.use_pool=True

class MultiprocSortQueueTest(ResultSortTest):

    def set_mode(self):
        self.mode = pypetconstants.WRAP_MODE_QUEUE
        self.multiproc = True
        self.ncores = 3
        self.use_pool=True


class MultiprocSortLockTest(ResultSortTest):

     def set_mode(self):
        self.mode = pypetconstants.WRAP_MODE_LOCK
        self.multiproc = True
        self.ncores = 4
        self.use_pool=True


class MultiprocNoPoolQueueTest(EnvironmentTest):

    def set_mode(self):
        EnvironmentTest.set_mode(self)
        self.mode = pypetconstants.WRAP_MODE_QUEUE
        self.multiproc = True
        self.ncores = 3
        self.use_pool=False


class MultiprocNoPoolLockTest(EnvironmentTest):

     def set_mode(self):
        EnvironmentTest.set_mode(self)
        self.mode = pypetconstants.WRAP_MODE_LOCK
        self.multiproc = True
        self.ncores = 2
        self.use_pool=False


class MultiprocNoPoolSortQueueTest(ResultSortTest):

    def set_mode(self):
        self.mode = pypetconstants.WRAP_MODE_QUEUE
        self.multiproc = True
        self.ncores = 3
        self.use_pool=False


class MultiprocNoPoolSortLockTest(ResultSortTest):

     def set_mode(self):
        self.mode = pypetconstants.WRAP_MODE_LOCK
        self.multiproc = True
        self.ncores = 3
        self.use_pool=False


class CapTest(EnvironmentTest):

    def setUp(self):

        self.multiproc = True
        self.mode = 'LOCK'

        logging.basicConfig(level = logging.INFO)

        self.trajname = make_trajectory_name(self)

        self.filename = make_temp_file(os.path.join('experiments',
                                                    'tests',
                                                    'HDF5',
                                                    '%s.hdf5' % self.trajname))
        self.logfolder = make_temp_file(os.path.join('experiments','tests','Log'))

        random.seed()


        env = Environment(trajectory=self.trajname,filename=self.filename,
                          file_title=self.trajname, log_folder=self.logfolder,
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
    make_run()