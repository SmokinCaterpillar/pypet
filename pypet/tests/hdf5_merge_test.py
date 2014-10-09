__author__ = 'Robert Meyer'




import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest


import numpy as np
from pypet.parameter import Parameter, PickleParameter, ArrayParameter, PickleResult
from pypet.utils.explore import cartesian_product
from pypet.environment import Environment
from pypet import pypetconstants, BaseParameter, BaseResult
import logging

from pypet.tests.test_helpers import add_params, create_param_dict, make_run, simple_calculations, \
    make_temp_file, TrajectoryComparator, multiply, make_trajectory_name
from pypet.tests.hdf5_storage_test import ResultSortTest


class MergeTest(TrajectoryComparator):


    def make_run(self,env):

        ### Make a test run
        simple_arg = -13
        simple_kwarg= 13.0
        env.f_run(simple_calculations, simple_arg, simple_kwarg=simple_kwarg)




    def make_environment(self, idx, filename):

        logging.basicConfig(level = logging.INFO)

        #self.filename = make_temp_file('experiments/tests/HDF5/test.hdf5')
        logfolder = make_temp_file('experiments/tests/Log')
        trajname = make_trajectory_name(self) + '__' +str(idx) +'_'

        env = Environment(trajectory=trajname,filename=filename,file_title=trajname,
                          log_folder=logfolder, log_stdout=False)


        self.envs.append(env)
        self.trajs.append( env.v_trajectory)

    def test_merging_trajectories_in_different_subspace(self):
        self.filenames = [make_temp_file('experiments/tests/HDF5/merge_diff_subspace.hdf5'), 0, 0]
        self.envs=[]
        self.trajs = []

        for irun,filename in enumerate(self.filenames):
            if isinstance(filename,int):
                filename = self.filenames[filename]

            self.make_environment( irun, filename)

        self.param_dict={}
        create_param_dict(self.param_dict)

        for irun in [0,1,2]:
            add_params(self.trajs[irun], self.param_dict)


        self.explore(self.trajs[0])
        self.explore2(self.trajs[1])
        self.compare_explore_diff_subspace(self.trajs[2])

        for irun in [0,1,2]:
            self.make_run(self.envs[irun])

        for irun in [0,1,2]:
            self.trajs[irun].f_update_skeleton()
            self.trajs[irun].f_load(load_parameters=pypetconstants.UPDATE_DATA,
                                    load_derived_parameters=pypetconstants.UPDATE_DATA,
                                    load_results=pypetconstants.UPDATE_DATA,
                                    load_other_data=pypetconstants.UPDATE_DATA)


        self.trajs[1].f_add_result('rrororo33o333o3o3oo3',1234567890)
        self.trajs[1].f_store_item('rrororo33o333o3o3oo3')
        self.trajs[2].f_add_result('rrororo33o333o3o3oo3',1234567890)
        self.trajs[2].f_store_item('rrororo33o333o3o3oo3')

        ##f_merge without destroying the original trajectory
        merged_traj = self.trajs[0]

        # We cannot copy nodes and delete the other trajectory
        with self.assertRaises(ValueError):
            merged_traj.f_merge(self.trajs[1], move_nodes=False, delete_other_trajectory=True,
                                trial_parameter='trial')



        merged_traj.f_merge(self.trajs[1], move_nodes=True,
                            delete_other_trajectory=True)

        merged_traj.f_load(load_parameters=pypetconstants.UPDATE_DATA,
                                    load_derived_parameters=pypetconstants.UPDATE_DATA,
                                    load_results=pypetconstants.UPDATE_DATA,
                                    load_other_data=pypetconstants.UPDATE_DATA)

        self.compare_trajectories(merged_traj,self.trajs[2])

    def test_merging_errors_if_trajs_do_not_match(self):

        self.filenames = [make_temp_file('experiments/tests/HDF5/merge_errors.hdf5'), 0]

        self.envs=[]
        self.trajs = []

        for irun,filename in enumerate(self.filenames):
            if isinstance(filename,int):
                filename = self.filenames[filename]

            self.make_environment( irun, filename)

        self.param_dict={}
        create_param_dict(self.param_dict)

        for irun in [0,1]:
            add_params(self.trajs[irun], self.param_dict)


        self.explore(self.trajs[0])
        self.explore(self.trajs[1])

        for irun in [0,1]:
            self.make_run(self.envs[irun])

        for irun in [0,1]:
            self.trajs[irun].f_update_skeleton()
            self.trajs[irun].f_load(load_parameters=pypetconstants.UPDATE_DATA,
                                    load_derived_parameters=pypetconstants.UPDATE_DATA,
                                    load_results=pypetconstants.UPDATE_DATA,
                                    load_other_data=pypetconstants.UPDATE_DATA)


        self.trajs[0].f_add_parameter('Merging.Denied', 13)

        ##f_merge without destroying the original trajectory
        merged_traj = self.trajs[0]

        # We cannot merge trajectories which parameters differ
        with self.assertRaises(TypeError):
            merged_traj.f_merge(self.trajs[1])

        self.trajs[1].f_add_parameter('Merging.Denied', 13.13)
        # We cannot merge trajectories where parameters differ in type
        with self.assertRaises(TypeError):
            merged_traj.f_merge(self.trajs[1])

        self.trajs[1].f_get('Denied').f_unlock()
        self.trajs[1].f_get('Denied').f_set(15)

        merged_traj.f_merge(self.trajs[1])




    def test_merge_basic_within_same_file_only_adding_more_trials_copy_nodes(self):
        self.filenames = [make_temp_file('experiments/tests/HDF5/merge1.hdf5'), 0, 0]
        self.merge_basic_only_adding_more_trials(True)

    def test_merge_basic_within_same_file_only_adding_more_trials_move_nodes(self):
        self.filenames = [make_temp_file('experiments/tests/HDF5/merge1.hdf5'), 0, 0]
        self.merge_basic_only_adding_more_trials(False)

    def test_basic_within_same_file_and_skipping_duplicates_which_will_be_all(self):
        self.filenames = [make_temp_file('experiments/tests/HDF5/merge1.hdf5'), 0]
        with self.assertRaises(ValueError):
            self.basic_and_skipping_duplicates_which_will_be_all()


    def test_basic_within_same_file_and_skipping_duplicates_which_leads_to_one_reamianing(self):
        self.filenames = [make_temp_file('experiments/tests/HDF5/merge1.hdf5'), 0, 0]
        self. basic_and_skipping_duplicates_which_leads_to_one_remaining()

    def test_basic_within_separate_file_and_skipping_duplicates_which_leads_to_one_reamianing(self):
        self.filenames = [make_temp_file('experiments/tests/HDF5/merge2.hdf5'),
                          make_temp_file('experiments/tests/HDF5/merge3.hdf5'),
                          make_temp_file('experiments/tests/HDF5/merge4.hdf5')]
        self. basic_and_skipping_duplicates_which_leads_to_one_remaining()



    def test_merge_basic_with_separate_files_only_adding_more_trials(self):
        self.filenames = [make_temp_file('experiments/tests/HDF5/merge2.hdf5'),
                          make_temp_file('experiments/tests/HDF5/merge3.hdf5'),
                          make_temp_file('experiments/tests/HDF5/merge4.hdf5')]
        self.merge_basic_only_adding_more_trials(True)

    def test_merge_basic_within_same_file_only_adding_more_trials_copy_nodes_test_backup(self):
        self.filenames = [make_temp_file('experiments/tests/HDF5/merge1.hdf5'), 0, 0]
        self.merge_basic_only_adding_more_trials_with_backup(True)

    def test_merge_basic_within_same_file_only_adding_more_trials_delete_other_trajectory(self):
        self.filenames = [make_temp_file('experiments/tests/HDF5/merge1.hdf5'), 0, 0]
        self.merge_basic_only_adding_more_trials(False, True)


    def merge_basic_only_adding_more_trials(self, copy_nodes, delete_traj=False):

        self.envs=[]
        self.trajs = []

        for irun,filename in enumerate(self.filenames):
            if isinstance(filename,int):
                filename = self.filenames[filename]

            self.make_environment( irun, filename)

        self.param_dict={}
        create_param_dict(self.param_dict)

        for irun in [0,1,2]:
            add_params(self.trajs[irun], self.param_dict)


        self.explore(self.trajs[0])
        self.explore(self.trajs[1])
        self.compare_explore_more_trials(self.trajs[2])

        for irun in [0,1,2]:
            self.make_run(self.envs[irun])

        for irun in [0,1,2]:
            self.trajs[irun].f_update_skeleton()
            self.trajs[irun].f_load(load_parameters=pypetconstants.UPDATE_DATA,
                                    load_derived_parameters=pypetconstants.UPDATE_DATA,
                                    load_results=pypetconstants.UPDATE_DATA,
                                    load_other_data=pypetconstants.UPDATE_DATA)


        self.trajs[1].f_add_result('rrororo33o333o3o3oo3',1234567890)
        self.trajs[1].f_store_item('rrororo33o333o3o3oo3')
        self.trajs[2].f_add_result('rrororo33o333o3o3oo3',1234567890)
        self.trajs[2].f_store_item('rrororo33o333o3o3oo3')

        ##f_merge without destroying the original trajectory
        merged_traj = self.trajs[0]

        # We cannot copy nodes and delete the other trajectory
        with self.assertRaises(ValueError):
            merged_traj.f_merge(self.trajs[1], move_nodes=False, delete_other_trajectory=True,
                                trial_parameter='trial')



        merged_traj.f_merge(self.trajs[1], move_nodes=not copy_nodes,
                            delete_other_trajectory=delete_traj,
                            trial_parameter='trial')

        merged_traj.f_load(load_parameters=pypetconstants.UPDATE_DATA,
                                    load_derived_parameters=pypetconstants.UPDATE_DATA,
                                    load_results=pypetconstants.UPDATE_DATA,
                                    load_other_data=pypetconstants.UPDATE_DATA)

        self.compare_trajectories(merged_traj,self.trajs[2])


    def merge_basic_only_adding_more_trials_with_backup(self,copy_nodes):


        self.envs=[]
        self.trajs = []

        for irun,filename in enumerate(self.filenames):
            if isinstance(filename,int):
                filename = self.filenames[filename]

            self.make_environment( irun, filename)

        self.param_dict={}
        create_param_dict(self.param_dict)

        for irun in [0,1,2]:
            add_params(self.trajs[irun],self.param_dict)


        self.explore(self.trajs[0])
        self.explore(self.trajs[1])
        self.compare_explore_more_trials(self.trajs[2])

        for irun in [0,1,2]:
            self.make_run(self.envs[irun])

        for irun in [0,1,2]:
            self.trajs[irun].f_update_skeleton()
            self.trajs[irun].f_load(load_parameters=pypetconstants.UPDATE_DATA,
                                    load_derived_parameters=pypetconstants.UPDATE_DATA,
                                    load_results=pypetconstants.UPDATE_DATA,
                                    load_other_data=pypetconstants.UPDATE_DATA)

        self.trajs[1].f_add_result('rrororo33o333o3o3oo3',1234567890)
        self.trajs[1].f_store_item('rrororo33o333o3o3oo3')
        self.trajs[2].f_add_result('rrororo33o333o3o3oo3',1234567890)
        self.trajs[2].f_store_item('rrororo33o333o3o3oo3')

        ##f_merge without destroying the original trajectory
        merged_traj = self.trajs[0]
        merged_traj.f_merge(self.trajs[1], move_nodes=not copy_nodes, delete_other_trajectory=False, trial_parameter='trial',
                            backup_filename=1)
        merged_traj.f_update_skeleton()
        merged_traj.f_load(load_results=pypetconstants.UPDATE_DATA,load_derived_parameters=pypetconstants.UPDATE_DATA,
                           load_parameters=pypetconstants.UPDATE_DATA,
                           load_other_data=pypetconstants.UPDATE_DATA)

        self.compare_trajectories(merged_traj,self.trajs[2])

    def basic_and_skipping_duplicates_which_leads_to_one_remaining(self):

        self.envs=[]
        self.trajs = []

        ntrajs = len(self.filenames)

        for irun,filename in enumerate(self.filenames):
            if isinstance(filename,int):
                filename = self.filenames[filename]

            self.make_environment( irun, filename)

        self.param_dict={}
        create_param_dict(self.param_dict)

        for irun in range(ntrajs):
            add_params(self.trajs[irun],self.param_dict)


        self.explore(self.trajs[0])
        self.explore_trials_differently(self.trajs[1])
        self.compare_explore_more_trials_with_removing_duplicates(self.trajs[2])

        for irun in range(ntrajs):
            self.make_run(self.envs[irun])

        for irun in range(ntrajs):
            self.trajs[irun].f_update_skeleton()
            self.trajs[irun].f_load(load_parameters=pypetconstants.UPDATE_DATA,
                                    load_derived_parameters=pypetconstants.UPDATE_DATA,
                                    load_results=pypetconstants.UPDATE_DATA,
                                    load_other_data=pypetconstants.UPDATE_DATA)


        self.trajs[1].f_add_result('rrororo33o333o3o3oo3',1234567890)
        self.trajs[1].f_store_item('rrororo33o333o3o3oo3')
        self.trajs[2].f_add_result('rrororo33o333o3o3oo3',1234567890)
        self.trajs[2].f_store_item('rrororo33o333o3o3oo3')

        ##f_merge without destroying the original trajectory
        merged_traj = self.trajs[0]
        merged_traj.f_merge(self.trajs[1], move_nodes=False, delete_other_trajectory=False, remove_duplicates=True)
        merged_traj.f_update_skeleton()
        merged_traj.f_load(load_parameters=pypetconstants.UPDATE_DATA,
                           load_derived_parameters=pypetconstants.UPDATE_DATA,
                           load_results=pypetconstants.UPDATE_DATA,
                           load_other_data=pypetconstants.UPDATE_DATA)

        self.compare_trajectories(merged_traj,self.trajs[2])

    def basic_and_skipping_duplicates_which_will_be_all(self):


        self.envs=[]
        self.trajs = []

        for irun,filename in enumerate(self.filenames):
            if isinstance(filename,int):
                filename = self.filenames[filename]

            self.make_environment( irun, filename)

        self.param_dict={}
        create_param_dict(self.param_dict)

        for irun in [0,1]:
            add_params(self.trajs[irun],self.param_dict)


        self.explore(self.trajs[0])
        self.explore(self.trajs[1])


        for irun in [0,1]:
            self.make_run(self.envs[irun])

        for irun in [0,1]:
            self.trajs[irun].f_update_skeleton()
            self.trajs[irun].f_load(load_parameters=pypetconstants.UPDATE_DATA,
                                    load_derived_parameters=pypetconstants.UPDATE_DATA,
                                    load_results=pypetconstants.UPDATE_DATA,
                                    load_other_data=pypetconstants.UPDATE_DATA)


        self.trajs[0].f_add_result('rrororo33o333o3o3oo3',1234567890)
        self.trajs[0].f_store_item('rrororo33o333o3o3oo3')
        self.trajs[1].f_add_result('rrororo33o333o3o3oo3',1234567890)
        self.trajs[1].f_store_item('rrororo33o333o3o3oo3')

        ##f_merge without destroying the original trajectory
        merged_traj = self.trajs[0]
        merged_traj.f_merge(self.trajs[1], move_nodes=False, delete_other_trajectory=False, remove_duplicates=True)
        merged_traj.f_update_skeleton()
        merged_traj.f_load(load_parameters=pypetconstants.UPDATE_DATA,
                           load_derived_parameters=pypetconstants.UPDATE_DATA,
                           load_results=pypetconstants.UPDATE_DATA,
                           load_other_data=pypetconstants.UPDATE_DATA)

        self.compare_trajectories(merged_traj,self.trajs[1])

    def explore(self, traj):
        self.explored ={'Normal.trial': [0,1],
            'Numpy.double': [np.array([1.0,2.0,3.0,4.0]), np.array([-1.0,3.0,5.0,7.0])]}

        traj.f_explore(cartesian_product(self.explored,  ('Numpy.double','Normal.trial')))


    def explore2(self, traj):
        self.explored2 ={'Normal.trial': [0,1],
            'Normal.int': [44, 45]}

        traj.f_explore(cartesian_product(self.explored2,  ('Normal.int','Normal.trial') ))

    def explore_trials_differently(self, traj):
        self.explored ={'Normal.trial': [0,1],
            'Numpy.double': [np.array([-1.0,2.0,3.0,5.0]), np.array([-1.0,3.0,5.0,7.0])]}

        traj.f_explore(cartesian_product(self.explored, ('Numpy.double','Normal.trial')))

    def compare_explore_diff_subspace(self,traj):
        self.explored ={'Normal.trial': [0,1,0,1,0,1,0,1],
            'Numpy.double': [np.array([1.0,2.0,3.0,4.0]),
                             np.array([1.0,2.0,3.0,4.0]),
                             np.array([-1.0,3.0,5.0,7.0]),
                             np.array([-1.0,3.0,5.0,7.0]),
                             np.array([1.0,2.0,3.0,4.0]),
                             np.array([1.0,2.0,3.0,4.0]),
                             np.array([1.0,2.0,3.0,4.0]),
                             np.array([1.0,2.0,3.0,4.0])],
            'Normal.int' : [42, 42, 42, 42, 44, 44, 45, 45]}

        traj.f_explore(self.explored)

    def compare_explore_more_trials_with_removing_duplicates(self,traj):
        self.explored ={'Normal.trial': [0,1,0,1,0,1],
            'Numpy.double': [np.array([1.0,2.0,3.0,4.0]),
                             np.array([1.0,2.0,3.0,4.0]),
                             np.array([-1.0,3.0,5.0,7.0]),
                             np.array([-1.0,3.0,5.0,7.0]),
                             np.array([-1.0,2.0,3.0,5.0]),
                             np.array([-1.0,2.0,3.0,5.0])]}

        traj.f_explore(self.explored)

    def compare_explore_more_trials(self,traj):
        self.explored ={'Normal.trial': [0,1,0,1,2,3,2,3],
            'Numpy.double': [np.array([1.0,2.0,3.0,4.0]),
                             np.array([1.0,2.0,3.0,4.0]),
                             np.array([-1.0,3.0,5.0,7.0]),
                             np.array([-1.0,3.0,5.0,7.0]),
                             np.array([1.0,2.0,3.0,4.0]),
                             np.array([1.0,2.0,3.0,4.0]),
                             np.array([-1.0,3.0,5.0,7.0]),
                             np.array([-1.0,3.0,5.0,7.0])]}




        traj.f_explore(self.explored)


class TestMergeResultsSort(ResultSortTest):

    def setUp(self):
        super(TestMergeResultsSort,self).setUp()

        env2 = Environment(trajectory=self.trajname+'2',filename=self.filename,
                          file_title=self.trajname, log_folder=self.logfolder,
                          log_stdout=False,
                          multiproc=self.multiproc,
                          wrap_mode=self.mode,
                          ncores=self.ncores)

        traj2 = env2.v_trajectory


        traj2.v_standard_parameter=Parameter

        traj2.f_add_parameter('x',0)
        traj2.f_add_parameter('y',0)

        self.env2=env2
        self.traj2=traj2

    def test_merge_normally(self):

        self.explore(self.traj)
        self.explore2(self.traj2)

        len1 = len(self.traj)
        len2 = len(self.traj2)

        self.assertTrue(len1==5)
        self.assertTrue(len2==5)

        self.env.f_run(multiply)
        self.env2.f_run(multiply)

        self.traj.f_merge(self.env2.v_trajectory)

        self.assertTrue(len(self.traj)==len1+len2)

        self.traj.f_load(load_results=pypetconstants.UPDATE_DATA)
        self.check_if_z_is_correct(self.traj)

    def test_merge_remove_duplicates(self):

        self.explore(self.traj)
        self.explore2(self.traj2)

        len1 = len(self.traj)
        len2 = len(self.traj2)

        self.assertTrue(len1==5)
        self.assertTrue(len2==5)

        self.env.f_run(multiply)
        self.env2.f_run(multiply)

        self.traj.f_merge(self.env2.v_trajectory,remove_duplicates=True)

        self.assertTrue(len(self.traj)==6)

        self.traj.f_load(load_results=pypetconstants.UPDATE_DATA)
        self.check_if_z_is_correct(self.traj)

    def explore(self,traj):
        self.explore_dict={'x':[0,1,2,3,4],'y':[1,1,2,2,3]}
        traj.f_explore(self.explore_dict)

    def explore2(self,traj):
        self.explore_dict={'x':[0,1,2,3,4],'y':[1,1,2,2,42]}
        traj.f_explore(self.explore_dict)



if __name__ == '__main__':
    make_run()