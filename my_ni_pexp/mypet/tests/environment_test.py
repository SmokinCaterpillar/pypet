__author__ = 'Robert Meyer'



import numpy as np
import unittest
from mypet.parameter import Parameter
from mypet.trajectory import Trajectory, SingleRun
from mypet.storageservice import LazyStorageService
from mypet.utils.explore import identity
from mypet.environment import Environment
import pickle
import logging
import cProfile

def just_printing_bro(traj):
        key = traj.get('Test').gfn()
        value = traj.get('par.Test', fast_access=True)
        print 'Current value of %s is %d' %(key, value)

class EnvironmentTest(unittest.TestCase):


    def setUp(self):

        logging.basicConfig(level = logging.DEBUG)

        self.filename = '../../Test/HDF5/test.hdf5'
        self.logfolder = '../../Test/Log'
        self.trajname = 'Test'

        env = Environment(self.trajname,self.filename,self.trajname,logfolder=self.logfolder)

        traj = env.get_trajectory()
        traj.set_storage_service(LazyStorageService())

        traj.ap('Test', 1)


        large_amount = 111

        for irun in range(large_amount):
            name = 'There.Are.Many.Of.m3' + str(irun)

            traj.ap(name, irun)

        traj.preset_config('ncores', 2)
        traj.preset_config('multiproc', True)

        traj.explore(identity,{traj.get('par.Test').gfn():[1,2,3,4,5]})

        self.traj = traj

        self.env = env
        self.traj = traj

    def test_multiprocessing(self):

        self.env.run(just_printing_bro)


if __name__ == '__main__':
    unittest.main()