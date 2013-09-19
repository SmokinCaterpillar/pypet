__author__ = 'Robert Meyer'



import numpy as np
import unittest
from pypet.parameter import Parameter
from pypet.trajectory import Trajectory, SingleRun
from pypet.storageservice import LazyStorageService
from pypet.utils.explore import identity
from pypet.environment import Environment
import pickle
import logging
import cProfile

def just_printing_bro(traj):
        key = traj.f_get('Test').gfn()
        value = traj.f_get('par.Test', fast_access=True)
        print 'Current value of %s is %d' %(key, value)

class EnvironmentTest(unittest.TestCase):


    def setUp(self):

        logging.basicConfig(level = logging.DEBUG)

        self.filename = '../../experiments/tests/HDF5/test.hdf5'
        self.logfolder = '../../experiments/tests/Log'
        self.trajname = 'Test'

        env = Environment(self.trajname,self.filename,self.trajname, log_folder=self.logfolder)

        traj = env.get_trajectory()
        traj.set_storage_service(LazyStorageService())

        traj.ap('Test', 1)


        large_amount = 111

        for irun in range(large_amount):
            name = 'There.Are.Many.Of.m3' + str(irun)

            traj.ap(name, irun)

        traj.f_preset_config('ncores', 2)
        traj.f_preset_config('multiproc', True)

        traj.f_explore({traj.f_get('par.Test').gfn():[1,2,3,4,5]})

        self.traj = traj

        self.env = env
        self.traj = traj

    def test_multiprocessing(self):

        self.env.run(just_printing_bro)


if __name__ == '__main__':
    unittest.main()