

__author__ = 'Robert Meyer'



import numpy as np
import unittest
from mypet.parameter import Parameter, PickleParameter, Result, BaseResult
from mypet.trajectory import Trajectory, SingleRun
from mypet.storageservice import LazyStorageService
from mypet.utils.explore import identity
import pickle
import logging
import cProfile
import scipy.sparse as spsp
import mypet.petexceptions as pex
import multiprocessing as multip

import mypet.storageservice as stsv

class ImAParameterInDisguise(Parameter):
    pass

class ImAResultInDisguise(Result):
    pass

class TrajectoryTest(unittest.TestCase):


    def setUp(self):
        name = 'Moop'

        self.traj = Trajectory(name,[ImAParameterInDisguise])

        comment = 'This is a comment'
        self.traj.add_comment(comment)

        self.assertTrue(comment == self.traj.get_comment())

        self.traj.add_parameter('IntParam',3)
        sparsemat = spsp.csr_matrix((1000,1000))
        sparsemat[1,2] = 17.777

        self.traj.add_parameter('SparseParam', sparsemat, param_type=PickleParameter)

        self.traj.add_parameter('FloatParam')

        self.traj.adp(Parameter('FortyTwo', 42))

        self.traj.add_result('Im.A.Simple.Result',44444,result_type=Result)

        self.traj.FloatParam=4.0

        self.traj.explore(identity,{'FloatParam':[1.0,1.1,1.2,1.3]})

        self.assertTrue(len(self.traj) == 4)



        with self.assertRaises(AttributeError):
            self.traj.ap('Peter.  h ._hurz')



    def testGet(self):
        self.traj.set_fast_access(True)
        self.traj.get('FloatParam', fast_access=True) == self.traj.FloatParam

        self.traj.set_fast_access(False)

        self.assertTrue(self.traj.get('FloatParam').get() == 4.0 , '%d != 4.0' %self.traj.get('FloatParam').get())

        self.assertTrue(self.traj.FortyTwo.get() == 42)


    def testremove(self):
        self.traj.remove_stuff(self.traj.get('FloatParam'))

        with self.assertRaises(AttributeError):
            self.traj.FloatParam

        self.assertFalse('FloatParam' in self.traj.to_dict())

        self.assertTrue(len(self.traj)==1)

        self.traj.remove_stuff('FortyTwo')

        self.traj.remove_stuff('SparseParam')
        self.traj.remove_stuff('IntParam')

        self.assertTrue(len(self.traj)==1)

    def test_changing(self):

        self.traj.preset_config('testconf', 1)
        self.traj.preset_parameter('testparam', 1)
        self.traj.preset_parameter('I_do_not_exist', 2)

        self.traj.ap('testparam', 0)
        self.traj.ac('testconf', 0)

        self.traj.set_fast_access(True)

        self.assertTrue(self.traj.testparam == 1)
        self.assertTrue(self.traj.testconf == 1)

        ### should raise an error because 'I_do_not_exist', does not exist:
        with self.assertRaises(pex.DefaultReplacementError):
            self.traj.prepare_experiment()


    def test_if_pickable(self):

        self.traj.set_fast_access(True)

        dump = pickle.dumps(self.traj)

        newtraj = pickle.loads(dump)


        self.assertTrue(len(newtraj) == len(self.traj))

        new_items = newtraj.to_dict(fast_access=True)

        for key, val in self.traj.to_dict(fast_access=True).items():
            #val = newtraj.get(key)
            nval = new_items[key]
            if isinstance(val, BaseResult):
                for ikey in val._data:
                    self.assertTrue(str(nval.get(ikey))==str(val.get(ikey)))
            else:

                self.assertTrue(str(val)==str(nval), '%s != %s' %(str(val),str(nval)))

    def test_dynamic_class_loading(self):
        self.traj.add_parameter('Rolf', 1.8,param_type = ImAParameterInDisguise, )

    def test_standard_change_param_change(self):
        self.traj.set_standard_parameter(ImAParameterInDisguise)

        self.traj.ap('I.should_be_not.normal')

        self.assertIsInstance(self.traj.get('normal'), ImAParameterInDisguise,'Param is %s insted of ParamInDisguise.' %str(type(self.traj.normal)))

        self.traj.set_standard_result(ImAResultInDisguise)

        self.traj.add_result('Peter.Parker')

        self.assertIsInstance(self.traj.Parker, ImAResultInDisguise)

class TrajectoryMergeTest(unittest.TestCase):

    def setUp(self):
        name = 'Moop'

        self.traj = Trajectory(name,[ImAParameterInDisguise])

        comment = 'This is a comment'
        self.traj.add_comment(comment)

        self.assertTrue(comment == self.traj.get_comment())

        self.traj.add_parameter('IntParam',3)
        sparsemat = spsp.csr_matrix((1000,1000))
        sparsemat[1,2] = 17.777

        #self.traj.add_parameter('SparseParam', sparsemat, param_type=PickleParameter)

        self.traj.add_parameter('FloatParam')

        self.traj.adp(Parameter('FortyTwo', 42))
        self.traj.ap('Trials',0)

        self.traj.add_result('Im.A.Simple.Result',44444,result_type=Result)

        self.traj.FloatParam=4.0
        self.traj.set_storage_service(LazyStorageService())


        self.traj.explore(identity,{'FloatParam':[1.0,1.1,1.2,1.3],'Trials':[0,1,2,3]})


        self.assertTrue(len(self.traj) == 4)


        name2 = 'aaaaah'
        self.traj2 = Trajectory(name2,[ImAParameterInDisguise])

        comment = 'This is a comment'
        self.traj2.add_comment(comment)

        self.assertTrue(comment == self.traj2.get_comment())

        self.traj2.add_parameter('IntParam',3)
        sparsemat = spsp.csr_matrix((1000,1000))
        sparsemat[1,2] = 17.777

        #self.traj2.add_parameter('SparseParam', sparsemat, param_type=PickleParameter)
        self.traj2.ap('Trials',0)

        self.traj2.add_parameter('FloatParam')

        self.traj2.adp(Parameter('FortyTwo', 42))

        self.traj2.add_result('Im.A.Simple.Result',44444,result_type=Result)

        self.traj2.FloatParam=4.0

        self.traj2.explore(identity,{'FloatParam':[42.0,43.0,1.2,1.3],'Trials':[0,1,2,3]})
        self.traj2.set_storage_service(LazyStorageService())

        self.assertTrue(len(self.traj2) == 4)



    def test_merge_parameters_without_remove(self):
        # remove_duplicates = True should be discarded by the trial parameter
        self.traj._merge_parameters(self.traj2,trial_parameter='Trials',remove_duplicates=True)

    def test_merge_parameters_with_remove(self):
        self.traj._merge_parameters(self.traj2,remove_duplicates=True)

    def test_merge_without_remove(self):
        self.traj.merge(self.traj2, remove_duplicates=True,trial_parameter='Trials')

    def test_merge_with_remove(self):
        self.traj.merge(self.traj2, remove_duplicates=True)

class SingleRunTest(unittest.TestCase):


    def setUp(self):

        logging.basicConfig(level = logging.INFO)
        traj = Trajectory('Test')

        traj.set_storage_service(LazyStorageService())

        large_amount = 111

        for irun in range(large_amount):
            name = 'There.Are.Many.Parameters.Like.Me' + str(irun)

            traj.ap(name, irun)


        traj.ap('TestExplorer', 1)

        traj.set_fast_access(False)
        traj.explore(identity,{traj.TestExplorer.gfn():[1,2,3,4,5]})
        traj.set_fast_access(True)

        self.traj = traj
        self.n = 1
        self.single_run = self.traj.make_single_run(self.n)
        self.assertTrue(len(self.single_run)==1)



    def test_if_single_run_can_be_pickled(self):

        self.single_run._storageservice=stsv.QueueStorageServiceSender()
        dump = pickle.dumps(self.single_run)

        single_run_rec = pickle.loads(dump)

        #print single_run.get('Test').val

        elements_dict = self.single_run.to_dict()
        for key in elements_dict:
            val = self.single_run.get(key,fast_access=True)
            val_rec = single_run_rec.get(key).get()
            self.assertTrue(np.all(val==val_rec))



    def test_adding_derived_parameter_and_result(self):
        value = 44.444
        self.single_run.add_derived_parameter('Im.A.Nice.Guy.Yo', value)
        self.assertTrue(self.single_run.Nice.Yo == value)

        self.single_run.add_result('Puberty.Hacks', val=value)
        resval= self.single_run.Hacks.get('val')
        self.assertTrue(resval == value)


    def test_standard_change_param_change(self):
        self.single_run.set_standard_parameter(ImAParameterInDisguise)

        self.single_run.ap('I.should_be_not.normal')

        self.assertIsInstance(self.single_run.get('normal'), ImAParameterInDisguise)

        self.single_run.set_standard_result(ImAResultInDisguise)

        self.single_run.add_result('Peter.Parker')

        self.assertIsInstance(self.single_run.Parker, ImAResultInDisguise)

class SingleRunQueueTest(unittest.TestCase):


    def setUp(self):

        logging.basicConfig(level = logging.INFO)
        traj = Trajectory('Test')

        traj.set_storage_service(LazyStorageService())

        large_amount = 111

        for irun in range(large_amount):
            name = 'There.Are.Many.Parameters.Like.Me' + str(irun)

            traj.ap(name, irun)


        traj.ap('TestExplorer', 1)

        traj.explore({traj.get('TestExplorer').gfn():[1,2,3,4,5]})

        self.traj = traj
        self.n = 1
        self.single_run = self.traj.make_single_run(self.n)
        self.assertTrue(len(self.single_run)==1)


    def test_queue(self):

        manager = multip.Manager()
        queue = manager.Queue()

        to_put = ('msg',[self.single_run],{})

        queue.put(to_put)

        pass


if __name__ == '__main__':
    unittest.main()