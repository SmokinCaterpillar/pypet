__author__ = 'Robert Meyer'


import numpy as np
from pypet.parameter import Parameter
from pypet.utils.explore import cartesian_product
from pypet.environment import Environment
from pypet import pypetconstants
import logging
import os
import time
from scipy.stats import pearsonr

from pypet.tests.testutils.ioutils import run_suite, make_temp_dir, make_trajectory_name, \
     parse_args, get_log_config
from pypet.tests.testutils.data import add_params, simple_calculations, TrajectoryComparator,\
    multiply, create_param_dict
from pypet.tests.integration.environment_test import ResultSortTest, my_set_func, my_run_func
from pypet import merge_all_in_folder


class MergeTest(TrajectoryComparator):

    tags = 'integration', 'hdf5', 'environment', 'merge'

    def tearDown(self):
        if hasattr(self, 'envs'):
            for env in self.envs:
                env.f_disable_logging()

        super(MergeTest, self).tearDown()

    def make_run(self,env):

        ### Make a test run
        simple_arg = -13
        simple_kwarg= 13.0
        env.f_run(simple_calculations, simple_arg, simple_kwarg=simple_kwarg)

    def make_environment(self, idx, filename, **kwargs):

        #self.filename = make_temp_dir('experiments/tests/HDF5/test.hdf5')
        logfolder = make_temp_dir(os.path.join('experiments','tests','Log'))
        trajname = make_trajectory_name(self) + '__' +str(idx) +'_'

        env = Environment(trajectory=trajname,filename=filename, file_title=trajname,
                          log_stdout=False,
                          large_overview_tables=True, log_config=get_log_config(),
                          **kwargs)


        self.envs.append(env)
        self.trajs.append( env.v_trajectory)

    def test_merging_trajectories_in_different_subspace(self):
        self.filenames = [make_temp_dir(os.path.join('experiments',
                                                      'tests',
                                                      'HDF5',
                                                      'merge_diff_subspace.hdf5')), 0, 0]
        self.envs=[]
        self.trajs = []

        for irun,filename in enumerate(self.filenames):
            if isinstance(filename,int):
                filename = self.filenames[filename]

            self.make_environment( irun, filename, wildcard_functions =
            {('$', 'crun') : my_run_func, ('$set', 'crunset'): my_set_func})

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
            self.trajs[irun].f_load_skeleton()
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

        merged_traj.f_merge(self.trajs[1], move_data=True,
                            delete_other_trajectory=True)

        merged_traj.f_load(load_parameters=pypetconstants.UPDATE_DATA,
                           load_derived_parameters=pypetconstants.UPDATE_DATA,
                           load_results=pypetconstants.UPDATE_DATA,
                           load_other_data=pypetconstants.UPDATE_DATA)

        self.compare_trajectories(merged_traj,self.trajs[2])

    def test_merging_errors_if_trajs_do_not_match(self):

        self.filenames = [make_temp_dir(os.path.join('experiments',
                                                      'tests',
                                                      'HDF5',
                                                      'merge_errors.hdf5')), 0]

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
            self.trajs[irun].f_load_skeleton()
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
        self.filenames = [make_temp_dir(os.path.join('experiments',
                                         'tests',
                                         'HDF5',
                                         'merge1.hdf5')), 0, 0]
        self.merge_basic_only_adding_more_trials(True)

    def test_merge_basic_within_same_file_only_adding_more_trials_move_nodes(self):
        self.filenames = [make_temp_dir(os.path.join('experiments',
                                         'tests',
                                         'HDF5',
                                         'merge1.hdf5')), 0, 0]
        self.merge_basic_only_adding_more_trials(False)

    def test_basic_within_same_file_and_skipping_duplicates_which_will_be_all(self):
        self.filenames = [make_temp_dir(os.path.join('experiments',
                                         'tests',
                                         'HDF5',
                                         'merge1.hdf5')), 0]
        with self.assertRaises(ValueError):
            self.basic_and_skipping_duplicates_which_will_be_all()


    def test_basic_within_same_file_and_skipping_duplicates_which_leads_to_one_reamianing(self):
        self.filenames = [make_temp_dir(os.path.join('experiments',
                                         'tests',
                                         'HDF5',
                                         'merge1_one_remaining.hdf5')), 0, 0]
        self. basic_and_skipping_duplicates_which_leads_to_one_remaining()

    def test_basic_within_separate_file_and_skipping_duplicates_which_leads_to_one_reamianing(self):
        self.filenames = [make_temp_dir(os.path.join('experiments',
                                         'tests',
                                         'HDF5',
                                         'merge2_one_remaining.hdf5')),
                          make_temp_dir(os.path.join('experiments',
                                         'tests',
                                         'HDF5',
                                         'merge3_one_remaining.hdf5')),
                          make_temp_dir(os.path.join('experiments',
                                         'tests',
                                         'HDF5',
                                         'merge4_one_remaining.hdf5'))]
        self. basic_and_skipping_duplicates_which_leads_to_one_remaining()

    def test_merge_basic_with_separate_files_only_adding_more_trials(self):
        self.filenames = [make_temp_dir(os.path.join('experiments',
                                         'tests',
                                         'HDF5',
                                         'merge2trials.hdf5')),
                          make_temp_dir(os.path.join('experiments',
                                         'tests',
                                         'HDF5',
                                         'merge3trials.hdf5')),
                          make_temp_dir(os.path.join('experiments',
                                         'tests',
                                         'HDF5',
                                         'merge4trials.hdf5'))]
        self.merge_basic_only_adding_more_trials(True)

    def test_merge_basic_with_separate_files_only_adding_more_trials_slow_merge(self):
        self.filenames = [make_temp_dir(os.path.join('experiments',
                                         'tests',
                                         'HDF5',
                                         'slow_merge2.hdf5')),
                          make_temp_dir(os.path.join('experiments',
                                         'tests',
                                         'HDF5',
                                         'slow_merge3.hdf5')),
                          make_temp_dir(os.path.join('experiments',
                                         'tests',
                                         'HDF5',
                                         'slow_merge4.hdf5'))]
        self.merge_basic_only_adding_more_trials(True, slow_merge=True)

    def test_merge_basic_within_same_file_only_adding_more_trials_copy_nodes_test_backup(self):
        self.filenames = [make_temp_dir(os.path.join('experiments',
                                         'tests',
                                         'HDF5',
                                         'merge1_more_trials.hdf5')), 0, 0]
        self.merge_basic_only_adding_more_trials_with_backup(True)

    def test_merge_basic_within_same_file_only_adding_more_trials_delete_other_trajectory(self):
        self.filenames = [make_temp_dir(os.path.join('experiments',
                                         'tests',
                                         'HDF5',
                                         'merge1_more_trials.hdf5')), 0, 0]
        self.merge_basic_only_adding_more_trials(False, True)


    def merge_basic_only_adding_more_trials(self, copy_nodes=False, delete_traj=False,
                                            slow_merge=False):

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
            self.trajs[irun].f_load_skeleton()
            self.trajs[irun].f_load(load_parameters=pypetconstants.UPDATE_DATA,
                                    load_derived_parameters=pypetconstants.UPDATE_DATA,
                                    load_results=pypetconstants.UPDATE_DATA,
                                    load_other_data=pypetconstants.UPDATE_DATA)


        self.trajs[1].f_add_result('gg.rrororo33o333o3o3oo3',1234567890)
        self.trajs[1].f_store_item('rrororo33o333o3o3oo3')
        self.trajs[1].res.gg.v_annotations['lala'] = 'Sonnenschein'
        self.trajs[1].f_store_item('gg')
        self.trajs[2].f_add_result('gg.rrororo33o333o3o3oo3',1234567890)
        self.trajs[2].f_store_item('rrororo33o333o3o3oo3')
        self.trajs[2].res.gg.v_annotations['lala'] = 'Sonnenschein'
        self.trajs[2].f_store_item('gg')

        ##f_merge without destroying the original trajectory
        merged_traj = self.trajs[0]

        self.trajs[1].f_remove_child('results', recursive=True)

        merged_traj.f_merge(self.trajs[1], move_data=not copy_nodes,
                            delete_other_trajectory=delete_traj,
                            trial_parameter='trial',
                            slow_merge=slow_merge)

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
            self.trajs[irun].f_load_skeleton()
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
        merged_traj.f_merge(self.trajs[1], move_data=not copy_nodes, delete_other_trajectory=False, trial_parameter='trial',
                            backup_filename=1)
        merged_traj.f_load_skeleton()
        merged_traj.f_load(load_parameters=pypetconstants.UPDATE_DATA,
                           load_derived_parameters=pypetconstants.UPDATE_DATA,
                           load_results=pypetconstants.UPDATE_DATA,
                           load_other_data=pypetconstants.UPDATE_DATA)

        self.compare_trajectories(merged_traj,self.trajs[2])

    def basic_and_skipping_duplicates_which_leads_to_one_remaining(self, slow_merge=False):

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
            self.trajs[irun].f_load_skeleton()
            self.trajs[irun].f_load(load_parameters=pypetconstants.UPDATE_DATA,
                                    load_derived_parameters=pypetconstants.UPDATE_DATA,
                                    load_results=pypetconstants.UPDATE_DATA,
                                    load_other_data=pypetconstants.UPDATE_DATA)


        self.trajs[1].f_add_result('rrororo33o333o3o3oo3',1234567890)
        self.trajs[1].f_store_item('rrororo33o333o3o3oo3')
        self.trajs[2].f_add_result('rrororo33o333o3o3oo3',1234567890)
        self.trajs[2].f_store_item('rrororo33o333o3o3oo3')

        run_name = pypetconstants.FORMATTED_RUN_NAME % 1
        run_name2 = pypetconstants.FORMATTED_RUN_NAME % 5
        self.trajs[1].f_add_result('%s.rrr' % run_name, 123)
        self.trajs[1].f_store_item('%s.rrr' % run_name)
        self.trajs[2].f_add_result('%s.rrr' % run_name2, 123)
        self.trajs[2].f_store_item('%s.rrr' % run_name2)

        self.trajs[1].f_add_result('Ignore.Me', 42)
        self.trajs[1].f_apar('Ignore.Me', 42)
        self.trajs[1].f_adpar('Ignore.Me', 42)

        ##f_merge without destroying the original trajectory
        merged_traj = self.trajs[0]
        merged_traj.f_merge(self.trajs[1], move_data=False,
                            delete_other_trajectory=False,
                            remove_duplicates=True,
                            ignore_data=('results.Ignore.Me', 'parameters.Ignore.Me',
                            'derived_parameters.Ignore.Me'),
                            slow_merge=slow_merge)
        merged_traj.f_load_skeleton()
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
            self.trajs[irun].f_load_skeleton()
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
        merged_traj.f_merge(self.trajs[1], move_data=False, delete_other_trajectory=False, remove_duplicates=True)
        merged_traj.f_load_skeleton()
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

    # def test_merging_wildcard(self):
    #     self.filenames = [make_temp_dir('experiments/tests/HDF5/merge_wild.hdf5'), 0, 0]
    #
    #     self.envs=[]
    #     self.trajs = []
    #
    #     for irun,filename in enumerate(self.filenames):
    #         if isinstance(filename,int):
    #             filename = self.filenames[filename]
    #
    #         self.make_environment( irun, filename)
    #
    #     self.trajs[0].f_add_derived_parameter('$', 45)
    #     self.trajs[1].f_add_derived_parameter('$', 47)
    #
    #     for traj in self.trajs:
    #         traj.f_store()
    #     self.trajs[0].f_merge(self.trajs[1])
    #     pass


class TestMergeResultsSort(ResultSortTest):

    tags = 'integration', 'hdf5', 'environment', 'merge'



    def setUp(self):
        super(TestMergeResultsSort,self).setUp()

        env2 = Environment(trajectory=self.trajname+'2',filename=self.filename,
                          file_title=self.trajname,
                          log_stdout=False,
                          log_config=get_log_config(),
                          multiproc=self.multiproc,
                          wrap_mode=self.mode,
                          ncores=self.ncores)

        traj2 = env2.v_trajectory


        traj2.v_standard_parameter=Parameter

        traj2.f_add_parameter('x',0)
        traj2.f_add_parameter('y',0)

        self.env2=env2
        self.traj2=traj2

    def tearDown(self):
        if hasattr(self, 'env'):
            self.env.f_disable_logging()
        if hasattr(self, 'env2'):
            self.env2.f_disable_logging()

        super(TestMergeResultsSort, self).tearDown()

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


class TestConsecutiveMerges(TrajectoryComparator):

    tags = 'integration', 'hdf5', 'environment', 'merge', 'consecutive_merge'

    def check_if_z_is_correct(self,traj):
        for x in range(len(traj)):
            traj.v_idx=x

            self.assertTrue(traj.crun.z==traj.x*traj.y,' z != x*y: %s != %s * %s' %
                                                  (str(traj.crun.z),str(traj.x),str(traj.y)))
        traj.v_idx=-1

    def set_mode(self):
        self.mode = 'LOCK'
        self.multiproc = False
        self.ncores = 1
        self.use_pool=True
        self.log_stdout=False
        self.freeze_input=False

    def explore(self,traj):
        self.explore_dict={'x':range(10),'y':range(10)}
        traj.f_explore(self.explore_dict)

    def setUp(self):
        self.envs = []
        self.trajs = []
        self.set_mode()

        self.filename = make_temp_dir(os.path.join('experiments','tests','HDF5','test.hdf5'))

        self.trajname = make_trajectory_name(self)

    def _make_env(self, idx, filename=None):
        if filename is None:
           filename = self.filename
        return Environment(trajectory=self.trajname+str(idx),filename=filename,
                          file_title=self.trajname,
                          log_stdout=False,
                          log_config=get_log_config(),
                          multiproc=self.multiproc,
                          wrap_mode=self.mode,
                          ncores=self.ncores)

    @staticmethod
    def strictly_increasing(L):
        return all(x<y for x, y in zip(L, L[1:]))

    def test_consecutive_merges(self):

        ntrajs = 41
        for irun in range(ntrajs):
            self.envs.append(self._make_env(irun))
            self.trajs.append(self.envs[-1].v_traj)
            self.trajs[-1].f_add_parameter('x',0)
            self.trajs[-1].f_add_parameter('y',0)
            self.explore(self.trajs[-1])

        for irun in range(ntrajs):
            self.envs[irun].f_run(multiply)

        merge_traj = self.trajs[0]
        merge_traj.f_load_skeleton()

        timings = []
        for irun in range(1, ntrajs):
            start = time.time()
            merge_traj.f_merge(self.trajs[irun], backup=False, consecutive_merge=True)
            end = time.time()
            delta = end -start
            timings.append(delta)

        # Test if there is no linear dependency for consecutive merges:
        if self.strictly_increasing(timings) and len(timings) > 1:
            raise ValueError('Timings %s are strictly increasing' % str(timings))
        r, alpha = pearsonr(range(len(timings)), timings)
        logging.error('R and Alpha of consecutive merge test %s' % str((r,alpha)))
        if alpha < 0.001 and r > 0:
            raise ValueError( 'R and Alpha of consecutive merge test %s\n' % str((r,alpha)),
                'Timings %s are lineary increasing' % str(timings))

        merge_traj.f_store()
        merge_traj.f_load(load_data=2)
        self.check_if_z_is_correct(merge_traj)

    def test_merge_all_in_folder(self):

        self.filename = make_temp_dir(os.path.join('experiments','tests','HDF5', 'subfolder',
                                                    'test.hdf5'))

        path, _ = os.path.split(self.filename)

        ntrajs = 4
        total_len = 0
        for irun in range(ntrajs):
            new_filename = os.path.join(path, 'test%d.hdf5' % irun)
            self.envs.append(self._make_env(irun, filename=new_filename))
            self.trajs.append(self.envs[-1].v_traj)
            self.trajs[-1].f_add_parameter('x',0)
            self.trajs[-1].f_add_parameter('y',0)
            self.explore(self.trajs[-1])
            total_len += len(self.trajs[-1])

        for irun in range(ntrajs):
            self.envs[irun].f_run(multiply)

        merge_traj = merge_all_in_folder(path, delete_other_files=True)
        merge_traj.f_load(load_data=2)

        self.assertEqual(len(merge_traj), total_len)
        self.check_if_z_is_correct(merge_traj)

    def test_merge_many(self):

        ntrajs = 4
        for irun in range(ntrajs):
            self.envs.append(self._make_env(irun))
            self.trajs.append(self.envs[-1].v_traj)
            self.trajs[-1].f_add_parameter('x',0)
            self.trajs[-1].f_add_parameter('y',0)
            self.explore(self.trajs[-1])

        for irun in range(ntrajs):
            self.envs[irun].f_run(multiply)

        merge_traj = self.trajs[0]

        total_len = 0
        for traj in self.trajs:
            total_len += len(traj)
        merge_traj.f_merge_many(self.trajs[1:])

        merge_traj.f_load(load_data=2)
        self.assertEqual(len(merge_traj), total_len)
        self.check_if_z_is_correct(merge_traj)

    def tearDown(self):
        for env in self.envs:
            env.f_disable_logging()
        super(TestConsecutiveMerges, self).tearDown()

if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)