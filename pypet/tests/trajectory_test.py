

__author__ = 'Robert Meyer'



import numpy as np
import unittest
from pypet.parameter import Parameter, PickleParameter, Result, BaseResult
from pypet.trajectory import Trajectory, SingleRun
from pypet.storageservice import LazyStorageService
import pickle
import logging
import cProfile
import scipy.sparse as spsp
import pypet.petexceptions as pex
import multiprocessing as multip

import pypet.storageservice as stsv

class ImAParameterInDisguise(Parameter):
    pass

class ImAResultInDisguise(Result):
    pass

class TrajectoryTest(unittest.TestCase):


    def setUp(self):
        name = 'Moop'

        self.traj = Trajectory(name,[ImAParameterInDisguise])

        comment = 'This is a comment'
        self.traj.v_comment=comment

        self.assertTrue(comment == self.traj.v_comment)

        self.traj.f_add_parameter('IntParam',3)
        sparsemat = spsp.csr_matrix((1000,1000))
        sparsemat[1,2] = 17.777

        self.traj.f_add_parameter(PickleParameter,'SparseParam', sparsemat)

        self.traj.f_add_parameter('FloatParam')

        self.traj.f_add_derived_parameter(Parameter('FortyTwo', 42))

        self.traj.f_add_result(Result,'Im.A.Simple.Result',44444)

        self.traj.FloatParam=4.0

        self.traj.f_explore({'FloatParam':[1.0,1.1,1.2,1.3]})

        self.assertTrue(len(self.traj) == 4)

        self.traj.f_add_parameter_group('peter.paul')

        self.traj.f_add_parameter('peter.markus.yve',6)

        self.traj.peter.f_add_parameter('paul.peter')

        with self.assertRaises(AttributeError):
            self.traj.markus.peter



        with self.assertRaises(AttributeError):
            self.traj.f_add_parameter('Peter.  h ._hurz')



    def testGet(self):
        self.traj.v_fast_access=True
        self.traj.f_get('FloatParam', fast_access=True) == self.traj.FloatParam

        self.traj.v_fast_access=False

        self.assertTrue(self.traj.f_get('FloatParam').f_get() == 4.0 , '%d != 4.0' %self.traj.f_get('FloatParam').f_get())

        self.assertTrue(self.traj.FortyTwo.f_get() == 42)


    def testremove(self):
        self.traj.f_remove_item(self.traj.f_get('peter.markus.yve'),remove_empty_groups=True)

        with self.assertRaises(AttributeError):
            self.traj.peter.markus.yve

        self.assertFalse('peter.markus.yve' in self.traj)

        #self.assertTrue(len(self.traj)==1)

        self.traj.f_remove_item('FortyTwo',remove_empyt_groups=True)

        self.traj.f_remove_item('SparseParam')
        self.traj.f_remove_item('IntParam')

        #self.assertTrue(len(self.traj)==1)

    def test_changing(self):

        self.traj.f_preset_config('testconf', 1)
        self.traj.f_preset_parameter('testparam', 1)
        self.traj.f_preset_parameter('I_do_not_exist', 2)

        self.traj.f_add_parameter('testparam', 0)
        self.traj.f_add_config('testconf', 0)

        self.traj.v_fast_access=True

        self.assertTrue(self.traj.testparam == 1)
        self.assertTrue(self.traj.testconf == 1)

        ### should raise an error because 'I_do_not_exist', does not exist:
        with self.assertRaises(pex.DefaultReplacementError):
            self.traj._prepare_experiment()


    def test_if_pickable(self):

        self.traj.v_fast_access=True

        #self.traj.v_full_copy=True
        dump = pickle.dumps(self.traj)

        newtraj = pickle.loads(dump)


        self.assertTrue(len(newtraj) == len(self.traj))

        new_items = newtraj.f_to_dict(fast_access=True)

        for key, val in self.traj.f_to_dict(fast_access=True).items():
            #val = newtraj.f_get(table_name)
            nval = new_items[key]
            if isinstance(val, BaseResult):
                for ikey in val._data:
                    self.assertTrue(str(nval.f_get(ikey))==str(val.f_get(ikey)))
            else:

                self.assertTrue(str(val)==str(nval), '%s != %s' %(str(val),str(nval)))

    def test_dynamic_class_loading(self):
        self.traj.f_add_parameter(ImAParameterInDisguise,'Rolf', 1.8)

    def test_standard_change_param_change(self):
        self.traj.v_standard_parameter=ImAParameterInDisguise

        self.traj.f_add_parameter('I.should_be_not.normal')

        self.assertIsInstance(self.traj.f_get('normal'), ImAParameterInDisguise,'Param is %s insted of ParamInDisguise.' %str(type(self.traj.normal)))

        self.traj.v_standard_result=ImAResultInDisguise

        self.traj.f_add_result('Peter.Parker')

        self.assertIsInstance(self.traj.Parker, ImAResultInDisguise)

class TrajectoryMergeTest(unittest.TestCase):

    def setUp(self):
        name = 'Moop'

        self.traj = Trajectory(name,[ImAParameterInDisguise])

        comment = 'This is a comment'
        self.traj.v_comment=comment

        self.assertTrue(comment == self.traj.v_comment)

        self.traj.f_add_parameter('IntParam',3)
        sparsemat = spsp.csr_matrix((1000,1000))
        sparsemat[1,2] = 17.777

        #self.traj.f_add_parameter('SparseParam', sparsemat, param_type=PickleParameter)

        self.traj.f_add_parameter('FloatParam')

        self.traj.f_add_derived_parameter(Parameter('FortyTwo', 42))
        self.traj.f_add_parameter('Trials',0)

        self.traj.f_add_result(Result,'Im.A.Simple.Result',44444)

        self.traj.FloatParam=4.0
        self.traj.v_storage_service = LazyStorageService()


        self.traj.f_explore({'FloatParam':[1.0,1.1,1.2,1.3],'Trials':[0,1,2,3]})


        self.assertTrue(len(self.traj) == 4)


        name2 = 'aaaaah'
        self.traj2 = Trajectory(name2,[ImAParameterInDisguise])

        comment = 'This is a comment'
        self.traj2.v_comment=comment

        self.assertTrue(comment == self.traj2.v_comment)

        self.traj2.f_add_parameter('IntParam',3)
        sparsemat = spsp.csr_matrix((1000,1000))
        sparsemat[1,2] = 17.777

        #self.traj2.f_add_parameter('SparseParam', sparsemat, param_type=PickleParameter)
        self.traj2.f_add_parameter('Trials',0)

        self.traj2.f_add_parameter('FloatParam')

        self.traj2.f_add_derived_parameter(Parameter('FortyTwo', 42))

        self.traj2.f_add_result(Result,'Im.A.Simple.Result',44444)

        self.traj2.FloatParam=4.0

        self.traj2.f_explore({'FloatParam':[42.0,43.0,1.2,1.3],'Trials':[0,1,2,3]})
        self.traj2.v_storage_service = LazyStorageService()

        self.assertTrue(len(self.traj2) == 4)



    def test_merge_parameters_without_remove(self):
        # remove_duplicates = True should be discarded by the trial parameter
        self.traj._merge_parameters(self.traj2,trial_parameter='Trials',remove_duplicates=True)

    def test_merge_parameters_with_remove(self):
        self.traj._merge_parameters(self.traj2,remove_duplicates=True)

    def test_merge_without_remove(self):
        self.traj.f_merge(self.traj2, remove_duplicates=True,trial_parameter='Trials')

    def test_merge_with_remove(self):
        self.traj.f_merge(self.traj2, remove_duplicates=True)

class SingleRunTest(unittest.TestCase):


    def setUp(self):

        logging.basicConfig(level = logging.INFO)
        traj = Trajectory('Test')

        traj.v_storage_service = LazyStorageService()

        large_amount = 111

        for irun in range(large_amount):
            name = 'There.Are.Many.Parameters.Like.Me' + str(irun)

            traj.f_add_parameter(name, irun)


        traj.f_add_parameter('TestExplorer', 1)

        traj.v_fast_access=False
        traj.f_explore({traj.TestExplorer.v_full_name:[1,2,3,4,5]})
        traj.v_fast_access=True

        self.traj = traj
        self.n = 1
        self.single_run = self.traj._make_single_run(self.n)
        self.assertTrue(len(self.single_run)==1)



    def test_if_single_run_can_be_pickled(self):

        self.single_run._storageservice=stsv.QueueStorageServiceSender()
        dump = pickle.dumps(self.single_run)

        single_run_rec = pickle.loads(dump)

        #print single_run.f_get('Test').val

        elements_dict = self.single_run.f_to_dict()
        for key in elements_dict:
            val = self.single_run.f_get(key,fast_access=True)
            val_rec = single_run_rec.f_get(key).f_get()
            self.assertTrue(np.all(val==val_rec))



    def test_adding_derived_parameter_and_result(self):
        value = 44.444
        self.single_run.f_add_derived_parameter('Im.A.Nice.Guy.Yo', value)
        self.assertTrue(self.single_run.Nice.Yo == value)

        self.single_run.f_add_result('Puberty.Hacks', val=value)
        resval= self.single_run.f_get('Hacks').f_get('val')
        self.assertTrue(resval == value, '%s != %s' % ( str(resval),str(value)))


    def test_standard_change_param_change(self):
        self.single_run.v_standard_parameter=ImAParameterInDisguise

        self.single_run.f_add_derived_parameter('I.should_be_not.normal')

        self.assertIsInstance(self.single_run.f_get('normal'), ImAParameterInDisguise)

        self.single_run.v_standard_result=ImAResultInDisguise

        self.single_run.f_add_result('Peter.Parker')

        self.assertIsInstance(self.single_run.Parker, ImAResultInDisguise)

class SingleRunQueueTest(unittest.TestCase):


    def setUp(self):

        logging.basicConfig(level = logging.INFO)
        traj = Trajectory('Test')

        traj.v_storage_service=LazyStorageService()

        large_amount = 11

        for irun in range(large_amount):
            name = 'There.Are.Many.Parameters.Like.Me' + str(irun)

            traj.f_add_parameter(name, irun)


        traj.f_add_parameter('TestExplorer', 1)

        traj.f_explore({traj.f_get('TestExplorer').v_full_name:[1,2,3,4,5]})

        self.traj = traj
        self.n = 1
        self.single_run = self.traj._make_single_run(self.n)
        self.assertTrue(len(self.single_run)==1)


    def test_queue(self):

        manager = multip.Manager()
        queue = manager.Queue()

        to_put = ('msg',[self.single_run],{})

        queue.put(to_put)

        pass


if __name__ == '__main__':
    unittest.main()