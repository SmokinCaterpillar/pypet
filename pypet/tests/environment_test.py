__author__ = 'Robert Meyer'





import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

from pypet.storageservice import LazyStorageService
from pypet.environment import Environment
import logging
from pypet.tests.test_helpers import make_run,make_temp_file, remove_data
import os


def just_printing_bro(traj):
        key = traj.f_get('Test').v_full_name
        value = traj.f_get('par.Test', fast_access=True)
        print('Current value of %s is %d' %(key, value))


class EnvironmentTest(unittest.TestCase):


    def setUp(self):

        logging.basicConfig(level = logging.INFO)

        self.filename = make_temp_file(os.path.join('experiments','tests', 'HDF5', 'test.hdf5'))
        self.logfolder = make_temp_file(os.path.join('experiments','tests','Log'))
        self.trajname = 'Test'

        env = Environment(trajectory=self.trajname,
                          filename=self.filename, log_folder=self.logfolder,
                          multiproc=True,
                          ncores=2)

        traj = env.v_trajectory
        traj.v_storage_service=LazyStorageService()

        traj.f_add_parameter('Test', 1)


        large_amount = 111

        for irun in range(large_amount):
            name = 'There.Are.Many.Of.m3' + str(irun)

            traj.f_add_parameter(name, irun)

        traj.f_explore({traj.f_get('par.Test').v_full_name:[1,2,3,4,5]})

        self.traj = traj

        self.env = env
        self.traj = traj

    def tearDown(self):
        self.env.f_disable_logging()
        remove_data()

    def test_multiprocessing(self):

        self.env.f_run(just_printing_bro)




if __name__ == '__main__':
    make_run()