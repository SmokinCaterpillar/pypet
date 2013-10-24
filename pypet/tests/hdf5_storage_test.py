

__author__ = 'Robert Meyer'

import numpy as np
from pypet.parameter import Parameter, PickleParameter, BaseResult, ArrayParameter, PickleResult, BaseParameter
from pypet.trajectory import Trajectory
from pypet.utils.explore import cartesian_product
from pypet.environment import Environment
from pypet.storageservice import HDF5StorageService
from pypet import pypetconstants
import logging
import pypet.pypetexceptions as pex

import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

import scipy.sparse as spsp
import random

import tables as pt

from test_helpers import add_params, create_param_dict, simple_calculations, make_run,\
    make_temp_file, TrajectoryComparator, multipy

class EnvironmentTest(TrajectoryComparator):


    def set_mode(self):
        self.mode = 'LOCK'
        self.multiproc = False
        self.ncores = 1


    def explore_complex_params(self, traj):
        matrices_csr = []
        for irun in range(3):

            spsparse_csr = spsp.csr_matrix((111,111))
            spsparse_csr[3,2+irun] = 44.5*irun

            matrices_csr.append(spsparse_csr)

        matrices_csc = []
        for irun in range(3):

            spsparse_csc = spsp.csc_matrix((111,111))
            spsparse_csc[3,2+irun] = 44.5*irun

            matrices_csc.append(spsparse_csc)

        matrices_bsr = []
        for irun in range(3):

            spsparse_bsr = spsp.csr_matrix((111,111))
            spsparse_bsr[3,2+irun] = 44.5*irun

            matrices_bsr.append(spsparse_bsr.tobsr())

        matrices_dia = []
        for irun in range(3):

            spsparse_dia = spsp.csr_matrix((111,111))
            spsparse_dia[3,2+irun] = 44.5*irun

            matrices_dia.append(spsparse_dia.todia())


        self.explore_dict={'string':[np.array(['Uno', 'Dos', 'Tres']),
                               np.array(['Cinco', 'Seis', 'Siette']),
                            np.array(['Ocho', 'Nueve', 'Diez'])],
                           'int':[1,2,3],
                           'csr_mat' : matrices_csr,
                           'csc_mat' : matrices_csc,
                           'bsr_mat' : matrices_bsr,
                           'dia_mat' : matrices_dia,
                           'list' : [['fff'],[444444,444,44,4,4,4],[1,2,3,42]]}

        with self.assertRaises(pex.NotUniqueNodeError):
            traj.f_explore(self.explore_dict)

        self.explore_dict={'Numpy.string':[np.array(['Uno', 'Dos', 'Tres']),
                               np.array(['Cinco', 'Seis', 'Siette']),
                            np.array(['Ocho', 'Nueve', 'Diez'])],
                           'Normal.int':[1,2,3],
                           'csr_mat' : matrices_csr,
                           'csc_mat' : matrices_csc,
                           'bsr_mat' : matrices_bsr,
                           'dia_mat' : matrices_dia,
                           'list' : [['fff'],[444444,444,44,4,4,4],[1,2,3,42]]}

        traj.f_explore(self.explore_dict)



    def explore(self, traj):
        self.explored ={'Normal.trial': [0],
            'Numpy.double': [np.array([1.0,2.0,3.0,4.0]), np.array([-1.0,3.0,5.0,7.0])],
            'csr_mat' :[spsp.csr_matrix((2222,22)), spsp.csr_matrix((2222,22))]}

        self.explored['csr_mat'][0][1,2]=44.0
        self.explored['csr_mat'][1][2,2]=33


        traj.f_explore(cartesian_product(self.explored))



    def setUp(self):
        self.set_mode()

        logging.basicConfig(level = logging.INFO)

        self.filename = make_temp_file('experiments/tests/HDF5/test.hdf5')
        self.logfolder = make_temp_file('experiments/tests/Log')

        random.seed()
        self.trajname = 'Test_' + self.__class__.__name__ + '_'+str(random.randint(0,10**10))

        env = Environment(trajectory=self.trajname,filename=self.filename,
                          file_title=self.trajname, log_folder=self.logfolder)

        traj = env.v_trajectory

        traj.multiproc = self.multiproc
        traj.wrap_mode = self.mode
        traj.ncores = self.ncores

        traj.v_standard_parameter=Parameter

        ## Create some parameters
        self.param_dict={}
        create_param_dict(self.param_dict)
        ### Add some parameter:
        add_params(traj,self.param_dict)

        #remember the trajectory and the environment
        self.traj = traj
        self.env = env



    def make_run(self):

        ### Make a test run
        simple_arg = -13
        simple_kwarg= 13.0
        self.env.f_run(simple_calculations,simple_arg,simple_kwarg=simple_kwarg)

    def test_run(self):
        self.traj.f_add_parameter('TEST', 'test_run')
        ###Explore
        self.explore(self.traj)

        ###Test, that you cannot append to data
        with self.assertRaises(ValueError):
            self.traj.f_store_item('multiproc')

        self.make_run()


        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj,newtraj)

    def test_run_complex(self):
        self.traj.f_add_parameter('TEST', 'test_run_complex')
        ###Explore
        self.explore_complex_params(self.traj)

        ###Test, that you cannot append to data
        with self.assertRaises(ValueError):
            self.traj.f_store_item('multiproc')

        self.make_run()


        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj,newtraj)

    def load_trajectory(self,trajectory_index=None,trajectory_name=None,as_new=False):
        ### Load The Trajectory and check if the values are still the same
        newtraj = Trajectory()
        newtraj.v_storage_service=HDF5StorageService(filename=self.filename)
        newtraj.f_load(name=trajectory_name, load_derived_parameters=2,load_results=2,
                       index=trajectory_index, as_new=as_new)
        return newtraj



    def test_expand(self):
        ###Explore
        self.traj.f_add_parameter('TEST', 'test_expand')
        self.explore(self.traj)

        self.make_run()

        self.expand()

        self.make_run()

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj,newtraj)

    def test_expand_after_reload(self):
        self.traj.f_add_parameter('TEST', 'test_expand_after_reload')
        ###Explore
        self.explore(self.traj)

        self.make_run()

        traj_name = self.traj.v_name

        traj_name = self.traj.v_name
        del self.env
        self.env = Environment(trajectory=self.traj,filename=self.filename,
                          file_title=self.trajname, log_folder=self.logfolder)

        self.traj = self.env.v_trajectory

        self.traj.f_load(name=traj_name)

        self.expand()

        self.make_run()

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj,newtraj)


    def expand(self):
        self.expanded ={'Normal.trial': [1],
            'Numpy.double': [np.array([1.0,2.0,3.0,4.0]), np.array([-1.0,3.0,5.0,7.0])],
            'csr_mat' :[spsp.csr_matrix((2222,22)), spsp.csr_matrix((2222,22))]}

        self.expanded['csr_mat'][0][1,2]=44.0
        self.expanded['csr_mat'][1][2,2]=33

        self.traj.f_expand(cartesian_product(self.expanded))


    ################## Overview TESTS #############################

    def test_switch_off_large_tables(self):
        self.traj.f_add_parameter('TEST', 'test_switch_off_LARGE_tables')
        ###Explore
        self.explore(self.traj)

        self.env.f_switch_off_large_overview()
        self.make_run()

        hdf5file = pt.openFile(self.filename)
        overview_group = hdf5file.getNode(where='/'+ self.traj.v_name, name='overview')
        should_not = ['derived_parameters_runs', 'results_runs']
        for name in should_not:
            self.assertTrue(not name in overview_group, '%s in overviews but should not!' % name)
        hdf5file.close()

    def test_switch_off_all_tables(self):
        ###Explore
        self.traj.f_add_parameter('TEST', 'test_switch_off_ALL_tables')
        self.explore(self.traj)

        self.env.f_switch_off_all_overview()
        self.make_run()

        hdf5file = pt.openFile(self.filename)
        overview_group = hdf5file.getNode(where='/'+ self.traj.v_name, name='overview')
        should_not = HDF5StorageService.NAME_TABLE_MAPPING.keys()
        for name in should_not:
            self.assertTrue(not name in overview_group, '%s in overviews but should not!' % name)

        hdf5file.close()


    def test_switch_on_all_comments(self):
        self.explore(self.traj)
        self.traj.purge_duplicate_comments=0

        self.make_run()

        hdf5file = pt.openFile(self.filename)
        traj_group = hdf5file.getNode(where='/', name= self.traj.v_name)

        for node in traj_group._f_walkGroups():
            if 'SRVC_LEAF' in node._v_attrs:
                self.assertTrue('SRVC_INIT_COMMENT' in node._v_attrs,
                                    'There is no comment in node %s!' % node._v_name)

        hdf5file.close()

    def test_purge_duplicate_comments_but_check_moving_comments_up_the_hierarchy(self):
        self.explore(self.traj)

        with self.assertRaises(RuntimeError):
            self.traj.purge_duplicate_comments=1
            self.traj.overview.results_runs_summary=0
            self.make_run()

        self.traj.f_get('purge_duplicate_comments').f_unlock()
        self.traj.purge_duplicate_comments=1
        self.traj.f_get('results_runs_summary').f_unlock()
        self.traj.overview.results_runs_summary=1

        # We fake that the trajectory starts with run_00000001
        self.traj._run_information['run_00000000']['completed']=1
        self.make_run()

        # Noe we make the first run
        self.traj._run_information['run_00000000']['completed']=0
        self.make_run()


        hdf5file = pt.openFile(self.filename)

        try:
            traj_group = hdf5file.getNode(where='/', name= self.traj.v_name)


            for node in traj_group._f_walkGroups():
                if 'SRVC_LEAF' in node._v_attrs:
                    if 'run_' in node._v_pathname:
                        #comment_run_name=self.get_comment_run_name(traj_group, node._v_pathname, node._v_name)
                        comment_run_name = 'run_00000000'
                        if comment_run_name in node._v_pathname:
                            self.assertTrue('SRVC_INIT_COMMENT' in node._v_attrs,
                                            'There is no comment in node %s!' % node._v_name)
                        else:
                            self.assertTrue(not ('SRVC_INIT_COMMENT' in node._v_attrs),
                                            'There is a comment in node %s!' % node._v_name)
                    else:
                        self.assertTrue('SRVC_INIT_COMMENT' in node._v_attrs,
                                    'There is no comment in node %s!' % node._v_name)
        finally:
            hdf5file.close()


    def test_purge_duplicate_comments(self):
        self.explore(self.traj)

        with self.assertRaises(RuntimeError):
            self.traj.purge_duplicate_comments=1
            self.traj.overview.results_runs_summary=0
            self.make_run()

        self.traj.f_get('purge_duplicate_comments').f_unlock()
        self.traj.purge_duplicate_comments=1
        self.traj.f_get('results_runs_summary').f_unlock()
        self.traj.overview.results_runs_summary=1
        self.make_run()


        hdf5file = pt.openFile(self.filename)

        try:
            traj_group = hdf5file.getNode(where='/', name= self.traj.v_name)


            for node in traj_group._f_walkGroups():
                if 'SRVC_LEAF' in node._v_attrs:
                    if 'run_' in node._v_pathname:
                        #comment_run_name=self.get_comment_run_name(traj_group, node._v_pathname, node._v_name)
                        comment_run_name = 'run_00000000'
                        if comment_run_name in node._v_pathname:
                            self.assertTrue('SRVC_INIT_COMMENT' in node._v_attrs,
                                            'There is no comment in node %s!' % node._v_name)
                        else:
                            self.assertTrue(not ('SRVC_INIT_COMMENT' in node._v_attrs),
                                            'There is a comment in node %s!' % node._v_name)
                    else:
                        self.assertTrue('SRVC_INIT_COMMENT' in node._v_attrs,
                                    'There is no comment in node %s!' % node._v_name)
        finally:
            hdf5file.close()

    #
    # def get_comment_run_name(self, traj_group, pathname, name):
    #
    #     if 'results' in pathname:
    #         overview_table = traj_group.overview.results_runs_summary
    #     else:
    #         overview_table = traj_group.overview.derived_parameters_runs_summary
    #
    #     for row in overview_table:
    #         if row['name']==name:
    #             comment_run_name =  row['example_item_run_name']
    #
    #     return comment_run_name


class ResultSortTest(TrajectoryComparator):

    def set_mode(self):
        self.mode = 'LOCK'
        self.multiproc = False
        self.ncores = 1

    def setUp(self):
        self.set_mode()
        logging.basicConfig(level = logging.INFO)

        self.filename = make_temp_file('experiments/tests/HDF5/test.hdf5')
        self.logfolder = make_temp_file('experiments/tests/Log')
        self.trajname = 'Test_' + self.__class__.__name__ + '_'+str(random.randint(0,10**10))

        env = Environment(trajectory=self.trajname,filename=self.filename,
                          file_title=self.trajname, log_folder=self.logfolder)

        traj = env.v_trajectory

        traj.multiproc = self.multiproc
        traj.wrap_mode = self.mode
        traj.ncores = self.ncores

        traj.v_standard_parameter=Parameter

        traj.f_add_parameter('x',0)
        traj.f_add_parameter('y',0)

        self.env=env
        self.traj=traj

    def load_trajectory(self,trajectory_index=None,trajectory_name=None,as_new=False):
        ### Load The Trajectory and check if the values are still the same
        newtraj = Trajectory()
        newtraj.v_storage_service=HDF5StorageService(filename=self.filename)
        newtraj.f_load(name=trajectory_name, load_derived_parameters=2,load_results=2,
                       index=trajectory_index, as_new=as_new)
        return newtraj


    def explore(self,traj):
        self.explore_dict={'x':[0,1,2,3,4],'y':[1,1,2,2,3]}
        traj.f_explore(self.explore_dict)


    def expand(self,traj):
        self.expand_dict={'x':[10,11,12,13],'y':[11,11,12,12]}
        traj.f_expand(self.expand_dict)


    def test_if_results_are_sorted_correctly(self):

        ###Explore
        self.explore(self.traj)


        self.env.f_run(multipy)
        traj = self.traj
        self.assertTrue(len(traj) == len(self.explore_dict.values()[0]))

        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj,newtraj)

    def test_expand(self):
        ###Explore
        self.explore(self.traj)

        self.env.f_run(multipy)
        traj = self.traj
        self.assertTrue(len(traj) == len(self.explore_dict.values()[0]))

        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        traj_name = self.env.v_trajectory.v_name
        del self.env
        self.env = Environment(trajectory=self.traj,filename=self.filename,
                          file_title=self.trajname, log_folder=self.logfolder)

        self.traj = self.env.v_trajectory

        self.traj.f_load(name=traj_name)

        self.expand(self.traj)

        self.env.f_run(multipy)
        traj = self.traj
        self.assertTrue(len(traj) == len(self.expand_dict.values()[0])+ len(self.explore_dict.values()[0]))


        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj,newtraj)

    def test_expand_after_reload(self):
        ###Explore
        self.explore(self.traj)

        self.env.f_run(multipy)
        traj = self.traj
        self.assertTrue(len(traj) == len(self.explore_dict.values()[0]))

        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        self.expand(self.traj)

        self.env.f_run(multipy)
        traj = self.traj
        self.assertTrue(len(traj) == len(self.expand_dict.values()[0])+ len(self.explore_dict.values()[0]))

        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj,newtraj)


    def check_if_z_is_correct(self,traj):
        for x in range(len(traj)):
            traj.v_idx=x

            self.assertTrue(traj.z==traj.x*traj.y,' z != x*y: %s != %s * %s' %
                                                  (str(traj.z),str(traj.x),str(traj.y)))
        traj.v_idx=-1




if __name__ == '__main__':
    make_run()