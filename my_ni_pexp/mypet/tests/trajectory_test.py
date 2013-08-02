__author__ = 'robert'



import numpy as np
import unittest
from mypet.parameter import Parameter
from mypet.trajectory import Trajectory, SingleRun
from mypet.storageservice import LazyStorageService
from mypet.utils.explore import identity
import pickle
import logging
import cProfile

class SingleRunTest(unittest.TestCase):


    def setUp(self):

        logging.basicConfig(level = logging.INFO)
        traj = Trajectory('Test')



        traj.set_storage_service(LazyStorageService())


        large_amount = 1111

        for irun in range(large_amount):
            name = 'L' + str(irun)

            traj.ap(name,value = irun)


        traj.ap('Test', value=1)

        traj.explore(identity,{traj.Test.gfn('value'):[1,2,3,4,5]})

        self.traj = traj



    def test_if_single_run_can_be_serialized(self):
        traj = self.traj

        single_run = traj.make_single_run(3)

        dump = pickle.dumps(single_run)

        single_run_rec = pickle.loads(dump)

        print single_run.get('Test').val

        elements_dict = single_run.to_dict()
        for key in elements_dict:
            val = single_run.get(key,fast_access=True)
            val_rec = single_run_rec.get(key).val
            self.assertEqual(val,val_rec)



if __name__ == '__main__':
    unittest.main()