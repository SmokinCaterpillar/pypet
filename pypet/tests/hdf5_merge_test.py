__author__ = 'Robert Meyer'



import numpy as np
import unittest
from pypet.parameter import BaseParameter,Parameter, PickleParameter, BaseResult, ArrayParameter, PickleResult
from pypet.utils.explore import cartesian_product
from pypet.environment import Environment
from pypet import globally
import logging
import cProfile
from pypet.utils.helpful_functions import flatten_dictionary
from pypet.utils.comparisons import results_equal,parameters_equal
import scipy.sparse as spsp
import shutil
import pandas as pd
from test_helpers import add_params, create_param_dict, run_tests, simple_calculations, \
    make_temp_file, TrajectoryComparator


REMOVE = True
SINGLETEST=[0]





class MergeTest(TrajectoryComparator):


    def make_run(self,env):

        ### Make a test run
        simple_arg = -13
        simple_kwarg= 13.0
        env.f_run(simple_calculations,simple_arg,simple_kwarg=simple_kwarg)




    def make_environment(self, idx, filename):

        logging.basicConfig(level = logging.DEBUG)

        #self.filename = make_temp_file('experiments/tests/HDF5/test.hdf5')
        logfolder = make_temp_file('experiments/tests/Log')
        trajname = 'Test%d' % idx

        env = Environment(trajectory=trajname,filename=filename,file_title=trajname, log_folder=logfolder)


        self.envs.append(env)
        self.trajs.append( env.v_trajectory)



    @unittest.skipIf(SINGLETEST != [0] and 1 not in SINGLETEST,'Skipping because, single debug is not pointing to the function ')
    def test_merge_basic_within_same_file_only_adding_more_trials_copy_nodes(self):
        self.filenames = [make_temp_file('experiments/tests/HDF5/merge1.hdf5'), 0, 0]
        self.merge_basic_only_adding_more_trials(True)

    @unittest.skipIf(SINGLETEST != [0] and 2 not in SINGLETEST,'Skipping because, single debug is not pointing to the function ')
    def test_merge_basic_within_same_file_only_adding_more_trials_move_nodes(self):
        self.filenames = [make_temp_file('experiments/tests/HDF5/merge1.hdf5'), 0, 0]
        self.merge_basic_only_adding_more_trials(False)

    @unittest.skipIf(SINGLETEST != [0] and 3 not in SINGLETEST,'Skipping because, single debug is not pointing to the function ')
    def test_basic_within_same_file_and_skipping_duplicates_which_will_be_all(self):
        self.filenames = [make_temp_file('experiments/tests/HDF5/merge1.hdf5'), 0]
        self.basic_and_skipping_duplicates_which_will_be_all()


    @unittest.skipIf(SINGLETEST != [0] and 4 not in SINGLETEST,'Skipping because, single debug is not pointing to the function ')
    def test_basic_within_same_file_and_skipping_duplicates_which_leads_to_one_reamianing(self):
        self.filenames = [make_temp_file('experiments/tests/HDF5/merge1.hdf5'), 0, 0]
        self. basic_and_skipping_duplicates_which_leads_to_one_remaining()


    @unittest.skipIf(SINGLETEST != [0] and 5 not in SINGLETEST,'Skipping because, single debug is not pointing to the function ')
    def test_merge_basic_within_same_file_only_adding_more_trials(self):
        self.filenames = [make_temp_file('experiments/tests/HDF5/merge2.hdf5'), make_temp_file('experiments/tests/HDF5/merge3.hdf5'), make_temp_file('experiments/tests/HDF5/merge4.hdf5')]
        self.merge_basic_only_adding_more_trials(True)

    @unittest.skipIf(SINGLETEST != [0] and 6 not in SINGLETEST,'Skipping because, single debug is not pointing to the function ')
    def test_merge_basic_within_same_file_only_adding_more_trials_copy_nodes_test_backup(self):
        self.filenames = [make_temp_file('experiments/tests/HDF5/merge1.hdf5'), 0, 0]
        self.merge_basic_only_adding_more_trials_with_backup(True)

    def merge_basic_only_adding_more_trials(self,copy_nodes):


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
            self.trajs[irun].f_load(load_parameters=globally.UPDATE_DATA,
                                    load_derived_parameters=globally.UPDATE_DATA,
                                    load_results=globally.UPDATE_DATA)


        self.trajs[1].f_add_result('rrororo33o333o3o3oo3',1234567890)
        self.trajs[1].f_store_item('rrororo33o333o3o3oo3')
        self.trajs[2].f_add_result('rrororo33o333o3o3oo3',1234567890)
        self.trajs[2].f_store_item('rrororo33o333o3o3oo3')

        ##f_merge without destroying the original trajectory
        merged_traj = self.trajs[0]
        merged_traj.f_merge(self.trajs[1], move_nodes=not copy_nodes,delete_trajectory=False, trial_parameter='trial')
        merged_traj.f_load(load_parameters=globally.UPDATE_DATA,
                                    load_derived_parameters=globally.UPDATE_DATA,
                                    load_results=globally.UPDATE_DATA)

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
            self.trajs[irun].f_load(load_parameters=globally.UPDATE_DATA,
                                    load_derived_parameters=globally.UPDATE_DATA,
                                    load_results=globally.UPDATE_DATA)


        self.trajs[1].f_add_result('rrororo33o333o3o3oo3',1234567890)
        self.trajs[1].f_store_item('rrororo33o333o3o3oo3')
        self.trajs[2].f_add_result('rrororo33o333o3o3oo3',1234567890)
        self.trajs[2].f_store_item('rrororo33o333o3o3oo3')

        ##f_merge without destroying the original trajectory
        merged_traj = self.trajs[0]
        merged_traj.f_merge(self.trajs[1], move_nodes=not copy_nodes,delete_trajectory=False, trial_parameter='trial',
                            backup_filename=1)
        merged_traj.f_update_skeleton()
        merged_traj.f_load(load_results=globally.UPDATE_DATA,load_derived_parameters=globally.UPDATE_DATA,
                           load_parameters=globally.UPDATE_DATA)

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
            self.trajs[irun].f_load(load_parameters=globally.UPDATE_DATA, load_derived_parameters=globally.UPDATE_DATA, load_results=globally.UPDATE_DATA)


        self.trajs[1].f_add_result('rrororo33o333o3o3oo3',1234567890)
        self.trajs[1].f_store_item('rrororo33o333o3o3oo3')
        self.trajs[2].f_add_result('rrororo33o333o3o3oo3',1234567890)
        self.trajs[2].f_store_item('rrororo33o333o3o3oo3')

        ##f_merge without destroying the original trajectory
        merged_traj = self.trajs[0]
        merged_traj.f_merge(self.trajs[1], move_nodes=False,delete_trajectory=False, remove_duplicates=True)
        merged_traj.f_update_skeleton()
        merged_traj.f_load(load_parameters=globally.UPDATE_DATA, load_derived_parameters=globally.UPDATE_DATA, load_results=globally.UPDATE_DATA)

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
            self.trajs[irun].f_load(load_parameters=globally.UPDATE_DATA, load_derived_parameters=globally.UPDATE_DATA, load_results=globally.UPDATE_DATA)


        self.trajs[0].f_add_result('rrororo33o333o3o3oo3',1234567890)
        self.trajs[0].f_store_item('rrororo33o333o3o3oo3')
        self.trajs[1].f_add_result('rrororo33o333o3o3oo3',1234567890)
        self.trajs[1].f_store_item('rrororo33o333o3o3oo3')

        ##f_merge without destroying the original trajectory
        merged_traj = self.trajs[0]
        merged_traj.f_merge(self.trajs[1], move_nodes=False,delete_trajectory=False, remove_duplicates=True)
        merged_traj.f_update_skeleton()
        merged_traj.f_load(load_parameters=globally.UPDATE_DATA, load_derived_parameters=globally.UPDATE_DATA, load_results=globally.UPDATE_DATA)

        self.compare_trajectories(merged_traj,self.trajs[1])


    def explore(self, traj):
        self.explored ={'Normal.trial': [0,1],
            'Numpy.double': [np.array([1.0,2.0,3.0,4.0]), np.array([-1.0,3.0,5.0,7.0])]}




        traj.f_explore(cartesian_product(self.explored))

    def explore_trials_differently(self, traj):
        self.explored ={'Normal.trial': [0,1],
            'Numpy.double': [np.array([-1.0,2.0,3.0,5.0]), np.array([-1.0,3.0,5.0,7.0])]}




        traj.f_explore(cartesian_product(self.explored))


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





if __name__ == '__main__':
    run_tests()