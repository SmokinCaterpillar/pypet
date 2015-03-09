__author__ = 'Robert Meyer'

import os
import platform
import logging
import time
import numpy as np

from pypet.trajectory import Trajectory, load_trajectory
from pypet.utils.explore import cartesian_product
from pypet.environment import Environment
from pypet.storageservice import HDF5StorageService
from pypet import pypetconstants, Result

import pypet.pypetexceptions as pex

import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

import scipy.sparse as spsp
import random
import pypet.compat as compat
import pypet.utils.ptcompat as ptcompat
from pypet import Parameter

import tables as pt

from pypet.tests.testutils.ioutils import  run_suite, make_temp_file,  make_trajectory_name,\
    get_log_level
from pypet.tests.testutils.data import create_param_dict, add_params, multiply,\
    simple_calculations, TrajectoryComparator


def add_one_particular_item(traj, store_full):
    traj.hi = 42, 'hi!'
    traj.f_store(store_full_in_run=store_full)
    traj.f_remove_child('hi')


class SlowResult(Result):
    def _load(self, load_dict):
        time.sleep(3)
        super(SlowResult, self)._load(load_dict)


class FullStorageTest(TrajectoryComparator):

    tags = 'integration', 'hdf5', 'environment'  # Test tags

    def test_multiple_loggers_defined(self):
        filename = make_temp_file('full_store.hdf5')
        logfolder = make_temp_file('logs')
        custom_logger = logging.getLogger('custom')
        root = logging.getLogger()
        logstr = 'TEST CUSTOM LOGGING!'
        rootstr = 'AAAAAAAAAAAA'
        with Environment(log_folder=logfolder, filename=filename,
                         logger_names=('', 'custom'),
                         log_levels=(logging.CRITICAL, logging.DEBUG)) as env:
            custom_logger.debug(logstr)
            root.debug(rootstr)

            logpath = env.v_log_path

        with open(os.path.join(logpath, 'main.txt'), 'r') as fh:
            text = fh.read()
            self.assertTrue(logstr in text)
            self.assertFalse(rootstr in text)

    def test_not_full_store(self):
        filename = make_temp_file('full_store.hdf5')
        logfolder = make_temp_file('logs')
        with Environment(log_folder=logfolder, filename=filename,
                         log_levels=get_log_level()) as env:

            traj = env.v_trajectory

            traj.par.x = 3, 'jj'

            traj.f_explore({'x': [1,2,3]})

            env.f_run(add_one_particular_item, False)

            traj = load_trajectory(index=-1, filename=filename)

            self.assertTrue('hi' not in traj)

    def test_full_store(self):
        filename = make_temp_file('full_store.hdf5')
        logfolder = make_temp_file('logs')
        with Environment(log_folder=logfolder, filename=filename,
                         log_levels=get_log_level()) as env:

            traj = env.v_trajectory

            traj.par.x = 3, 'jj'

            traj.f_explore({'x': [1,2,3]})

            env.f_run(add_one_particular_item, True)

            traj = load_trajectory(index=-1, filename=filename)

            self.assertTrue('hi' in traj)


def add_large_data(traj):
    np_array = np.random.rand(100,1000,10)
    traj.f_add_result('l4rge', np_array)
    traj.f_store_item('l4rge')
    traj.f_remove_item('l4rge')

    array_list = []
    for irun in range(1000):
        array_list.append(np.random.rand(10))
    traj.f_add_result('m4ny', *array_list)

class EnvironmentTest(TrajectoryComparator):

    tags = 'integration', 'hdf5', 'environment'

    def set_mode(self):
        self.mode = 'LOCK'
        self.multiproc = False
        self.ncores = 1
        self.use_pool=True
        self.pandas_format='fixed'
        self.pandas_append=False
        self.complib = 'blosc'
        self.complevel=9
        self.shuffle=True
        self.fletcher32 = False
        self.encoding = 'utf8'
        self.log_stdout=False

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
        traj.f_shrink(force=True)

        par_dict = traj.parameters.f_to_dict()
        for param_name in par_dict:
            param = par_dict[param_name]
            if param.v_name in self.explore_dict:
                param.f_unlock()
                if param.v_explored:
                    param._shrink()

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

    def explore_large(self, traj):
        self.explored ={'Normal.trial': [0,1]}
        traj.f_explore(cartesian_product(self.explored))

    def tearDown(self):
        self.env.f_disable_logging()

        super(EnvironmentTest, self).tearDown()

    def setUp(self):
        self.set_mode()
        self.logfolder = make_temp_file(os.path.join('experiments',
                                                      'tests',
                                                      'Log'))

        random.seed()
        self.trajname = make_trajectory_name(self)
        self.filename = make_temp_file(os.path.join('experiments',
                                                    'tests',
                                                    'HDF5',
                                                    'test%s.hdf5' % self.trajname))

        env = Environment(trajectory=self.trajname, filename=self.filename,
                          file_title=self.trajname, log_folder=self.logfolder,
                          log_stdout=self.log_stdout,
                          log_levels=get_log_level(),
                          results_per_run=5,
                          derived_parameters_per_run=5,
                          multiproc=self.multiproc,
                          ncores=self.ncores,
                          wrap_mode=self.mode,
                          use_pool=self.use_pool,
                          fletcher32=self.fletcher32,
                          complevel=self.complevel,
                          complib=self.complib,
                          shuffle=self.shuffle,
                          pandas_append=self.pandas_append,
                          pandas_format=self.pandas_format,
                          encoding=self.encoding)

        traj = env.v_trajectory

        traj.v_standard_parameter=Parameter

        ## Create some parameters
        self.param_dict={}
        create_param_dict(self.param_dict)
        ### Add some parameter:
        add_params(traj,self.param_dict)

        #remember the trajectory and the environment
        self.traj = traj
        self.env = env

    def test_file_overwriting(self):
        self.traj.f_store()

        with ptcompat.open_file(self.filename, mode='r') as file:
            nchildren = len(file.root._v_children)
            self.assertTrue(nchildren > 0)

        env2 = Environment(filename=self.filename, log_folder=None, log_levels=get_log_level())
        traj2 = env2.v_trajectory
        traj2.f_store()

        self.assertTrue(os.path.exists(self.filename))

        with ptcompat.open_file(self.filename, mode='r') as file:
            nchildren = len(file.root._v_children)
            self.assertTrue(nchildren > 1)

        env3 = Environment(filename=self.filename, overwrite_file=True, log_folder=None,
                           log_levels=get_log_level())

        self.assertFalse(os.path.exists(self.filename))

        env2.f_disable_logging()
        env3.f_disable_logging()

    def test_time_display_of_loading(self):
        filename = make_temp_file('sloooow.hdf5')
        log_folder = make_temp_file('logs')
        env = Environment(trajectory='traj', add_time=True, filename=filename,
                          log_stdout=False, log_levels=logging.INFO, # needed for the test!
                          dynamic_imports=SlowResult, log_folder=log_folder,
                          display_time=1)
        traj = env.v_traj
        res=traj.f_add_result(SlowResult, 'iii', 42, 43, comment='llk')
        traj.f_store()
        traj.f_load(load_data=3)

        path = env.v_log_path
        mainfilename = os.path.join(path, 'main.txt')
        with open(mainfilename, mode='r') as mainf:
            full_text = mainf.read()
            self.assertTrue('nodes/s)' in full_text)

        env.f_disable_logging()

    def make_run_large_data(self):
        self.env.f_run(add_large_data)

    def make_run(self):

        ### Make a test run
        simple_arg = -13
        simple_kwarg= 13.0
        self.env.f_run(simple_calculations,simple_arg,simple_kwarg=simple_kwarg)

    def test_a_large_run(self):
        logging.getLogger().info('Testing large run')
        self.traj.f_add_parameter('TEST', 'test_run')
        ###Explore
        self.explore_large(self.traj)
        self.make_run_large_data()

        # Check if printing and repr work
        logging.getLogger().info(str(self.env))
        logging.getLogger().info(repr(self.env))

        newtraj = Trajectory()
        newtraj.f_load(name=self.traj.v_name, as_new=False, load_data=2, filename=self.filename)

        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj,newtraj)

        size=os.path.getsize(self.filename)
        size_in_mb = size/1000000.
        logging.getLogger().info('Size is %sMB' % str(size_in_mb))
        self.assertTrue(size_in_mb < 30.0, 'Size is %sMB > 30MB' % str(size_in_mb))

    def test_run(self):
        self.traj.f_add_parameter('TEST', 'test_run')
        ###Explore
        self.explore(self.traj)

        self.make_run()

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj, newtraj)

        size=os.path.getsize(self.filename)
        size_in_mb = size/1000000.
        logging.getLogger().info('Size is %sMB' % str(size_in_mb))
        self.assertTrue(size_in_mb < 6.0, 'Size is %sMB > 6MB' % str(size_in_mb))

    def test_just_one_run(self):
        self.make_run()
        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj, newtraj)

        self.assertTrue(len(newtraj) == 1)

        size=os.path.getsize(self.filename)
        size_in_mb = size/1000000.
        logging.getLogger().info('Size is %sMB' % str(size_in_mb))
        self.assertTrue(size_in_mb < 2.0, 'Size is %sMB > 6MB' % str(size_in_mb))

        with self.assertRaises(TypeError):
            self.explore(self.traj)


    @unittest.skipIf(platform.system() == 'Windows', 'Log file creation might fail under windows.')
    def test_logfile_creation(self):
        # if not self.multiproc:
        #     return
        self.traj.f_add_parameter('TEST', 'test_run')
        ###Explore
        self.explore(self.traj)

        self.make_run()

        log_path = self.env.v_log_path

        file_list = [file for file in os.listdir(log_path)]

        if self.multiproc:
            if self.mode == 'LOCK':
                length = len(self.traj) + 2
            elif self.mode == 'QUEUE':
                length = len(self.traj) + 3
            else:
                raise RuntimeError('You shall not pass!')
        else:
            length = 2

        self.assertTrue(len(file_list) == length ) # assert that there are as many
        # files as runs plus main.txt and errors and warnings

        for file in file_list:
            if 'main.txt' in file:
                pass
            elif 'errors_and_warnings.txt' in file:
                pass
            elif 'process' in file:
                pass
            elif 'poolworker' in file:
                pass
            elif 'queue' in file:
                pass
            else:
                self.assertTrue(False, 'There`s a file in the log folder that does not '
                                       'belong there: %s' % str(file))


    def test_run_complex(self):
        self.traj.f_add_parameter('TEST', 'test_run_complex')
        ###Explore
        self.explore_complex_params(self.traj)

        self.make_run()


        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj, newtraj)

    def load_trajectory(self,trajectory_index=None,trajectory_name=None,as_new=False):
        ### Load The Trajectory and check if the values are still the same
        newtraj = Trajectory()
        newtraj.v_storage_service=HDF5StorageService(filename=self.filename)
        newtraj.f_load(name=trajectory_name, index=trajectory_index, as_new=as_new,
                       load_parameters=2, load_derived_parameters=2, load_results=2,
                       load_other_data=2)
        return newtraj


    def test_expand(self):

        ###Explore
        self.traj.f_add_parameter('TEST', 'test_expand')
        self.explore(self.traj)

        self.make_run()

        self.expand()

        logging.getLogger().info('\n $$$$$$$$$$$$$$$$$ Second Run $$$$$$$$$$$$$$$$$$$$$$$$')
        self.make_run()

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj,newtraj)

    def test_expand_after_reload(self):

        self.traj.f_add_parameter('TEST', 'test_expand_after_reload')
        ###Explore
        self.explore(self.traj)

        self.make_run()

        traj_name = self.traj.v_name

        traj_name = self.traj.v_name


        self.env = Environment(trajectory=self.traj, log_folder=self.logfolder,
                          log_stdout=False, log_levels=get_log_level())

        self.traj = self.env.v_trajectory

        self.traj.f_load(name=traj_name)

        self.expand()

        logging.getLogger().info('\n $$$$$$$$$$$$ Second Run $$$$$$$$$$ \n')
        self.make_run()

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj, newtraj)


    def expand(self):
        self.expanded ={'Normal.trial': [1],
            'Numpy.double': [np.array([1.0,2.0,3.0,4.0]), np.array([-1.0,3.0,5.0,7.0])],
            'csr_mat' :[spsp.csr_matrix((2222,22)), spsp.csr_matrix((2222,22))]}

        self.expanded['csr_mat'][0][1,2]=44.0
        self.expanded['csr_mat'][1][2,2]=33

        self.traj.f_expand(cartesian_product(self.expanded))


    ################## Overview TESTS #############################

    def test_switch_ON_large_tables(self):
        self.traj.f_add_parameter('TEST', 'test_switch_off_LARGE_tables')
        ###Explore
        self.explore(self.traj)

        self.env.f_set_large_overview(True)
        self.make_run()

        hdf5file = pt.openFile(self.filename)
        overview_group = hdf5file.getNode(where='/'+ self.traj.v_name, name='overview')
        should_not = ['derived_parameters_runs', 'results_runs']
        for name in should_not:
            self.assertTrue(name in overview_group, '%s in overviews but should not!' % name)
        hdf5file.close()

        self.traj.f_load(load_parameters=2, load_derived_parameters=2, load_results=2)
        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name)

        self.compare_trajectories(newtraj,self.traj)

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
            name = name.split('.')[-1] # Get only the name of the table, no the full name
            self.assertTrue(not name in overview_group, '%s in overviews but should not!' % name)

        hdf5file.close()


    def test_store_form_tuple(self):
        self.traj.f_store()

        self.traj.f_add_result('TestResItem', 42, 43)

        with self.assertRaises(ValueError):
             self.traj.f_store_item((pypetconstants.LEAF, self.traj.TestResItem,(),{},5))

        self.traj.f_store_item((pypetconstants.LEAF, self.traj.TestResItem))

        self.traj.results.f_remove_child('TestResItem')

        self.assertTrue('TestResItem' not in self.traj)

        self.traj.results.f_load_child('TestResItem', load_data=pypetconstants.LOAD_SKELETON)

        self.traj.f_load_item((pypetconstants.LEAF,self.traj.TestResItem,(),{'load_only': 'TestResItem'}))

        self.assertTrue(self.traj.TestResItem, 42)

    def test_store_single_group(self):
        self.traj.f_store()

        self.traj.f_add_parameter_group('new.test.group').v_annotations.f_set(42)

        self.traj.f_store_item('new.group')


        # group is below test not new, so ValueError thrown:
        with self.assertRaises(ValueError):
            self.traj.parameters.new.f_remove_child('group')

        # group is below test not new, so ValueError thrown:
        with self.assertRaises(ValueError):
            self.traj.parameters.new.f_store_child('group')

        # group has children and recursive is false
        with self.assertRaises(TypeError):
            self.traj.parameters.new.f_remove_child('test')


        self.traj.new.f_remove_child('test', recursive=True)

        self.assertTrue('new.group' not in self.traj)

        self.traj.new.f_load_child('test', recursive=True, load_data=pypetconstants.LOAD_SKELETON)

        self.assertTrue(self.traj.new.group.v_annotations.annotation, 42)

        self.traj.f_delete_item('new.test.group')

        with self.assertRaises(pex.DataNotInStorageError):
            self.traj.parameters.f_load_child('new.test.group',
                                              load_data=pypetconstants.LOAD_SKELETON)

    def test_switch_on_all_comments(self):
        self.explore(self.traj)
        self.traj.hdf5.purge_duplicate_comments=0

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
            self.traj.hdf5.purge_duplicate_comments=1
            self.traj.overview.results_runs_summary=0
            self.make_run()

        self.traj.f_get('purge_duplicate_comments').f_unlock()
        self.traj.hdf5.purge_duplicate_comments=1
        self.traj.f_get('results_runs_summary').f_unlock()
        self.traj.overview.results_runs_summary=1

        # We fake that the trajectory starts with run_00000001
        self.traj._run_information['run_00000000']['completed']=1
        self.make_run()

        # Now we make the first run
        self.traj._run_information['run_00000000']['completed']=0
        self.make_run()


        hdf5file = pt.openFile(self.filename, mode='a')

        try:
            traj_group = hdf5file.getNode(where='/', name= self.traj.v_name)


            for node in traj_group._f_walkGroups():
                if 'SRVC_LEAF' in node._v_attrs:
                    if ('run_' in node._v_pathname and
                            not pypetconstants.RUN_NAME_DUMMY in node._v_pathname):
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
            self.traj.hdf5.purge_duplicate_comments = 1
            self.traj.overview.results_runs_summary = 0
            self.make_run()

        self.traj.f_get('purge_duplicate_comments').f_unlock()
        self.traj.hdf5.purge_duplicate_comments=1
        self.traj.f_get('results_runs_summary').f_unlock()
        self.traj.overview.results_runs_summary=1
        self.make_run()


        hdf5file = pt.openFile(self.filename, mode='a')

        try:
            traj_group = hdf5file.getNode(where='/', name= self.traj.v_name)


            for node in traj_group._f_walkGroups():
                if 'SRVC_LEAF' in node._v_attrs:
                    if ('run_' in node._v_pathname and
                            not pypetconstants.RUN_NAME_DUMMY in node._v_pathname):
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


class TestOtherHDF5Settings(EnvironmentTest):

    tags = 'integration', 'hdf5', 'environment', 'hdf5_settings'

    def set_mode(self):
        EnvironmentTest.set_mode(self)
        self.mode = 'LOCK'
        self.multiproc = False
        self.ncores = 1
        self.use_pool=True
        self.pandas_format='table'
        self.pandas_append=True
        self.complib = 'zlib'
        self.complevel=2
        self.shuffle=False
        self.fletcher32 = False
        self.encoding='latin1'


class TestOtherHDF5Settings2(EnvironmentTest):

    tags = 'integration', 'hdf5', 'environment', 'hdf5_settings'

    def set_mode(self):
        EnvironmentTest.set_mode(self)
        self.mode = 'LOCK'
        self.multiproc = False
        self.ncores = 1
        self.use_pool=True
        self.pandas_format='table'
        self.pandas_append=False
        self.complib = 'lzo'
        self.complevel=2
        self.shuffle=False
        self.fletcher32 = True
        self.encoding='latin1'



class ResultSortTest(TrajectoryComparator):

    tags = 'integration', 'hdf5', 'environment'

    def set_mode(self):
        self.mode = 'LOCK'
        self.multiproc = False
        self.ncores = 1
        self.use_pool=True
        self.log_stdout=False

    def tearDown(self):
        self.env.f_disable_logging()
        super(ResultSortTest, self).tearDown()

    def setUp(self):
        self.set_mode()

        self.filename = make_temp_file(os.path.join('experiments','tests','HDF5','test.hdf5'))
        self.logfolder = make_temp_file(os.path.join('experiments',
                                                      'tests',
                                                      'Log'))
        self.trajname = make_trajectory_name(self)

        env = Environment(trajectory=self.trajname,filename=self.filename,
                          file_title=self.trajname, log_folder=self.logfolder,
                          log_stdout=self.log_stdout,
                          log_levels=get_log_level(),
                          multiproc=self.multiproc,
                          wrap_mode=self.mode,
                          ncores=self.ncores,
                          use_pool=self.use_pool)

        traj = env.v_trajectory


        traj.v_standard_parameter=Parameter

        traj.f_add_parameter('x',0)
        traj.f_add_parameter('y',0)

        self.env=env
        self.traj=traj

    def load_trajectory(self,trajectory_index=None,trajectory_name=None,as_new=False):
        ### Load The Trajectory and check if the values are still the same
        newtraj = Trajectory()
        newtraj.v_storage_service=HDF5StorageService(filename=self.filename)
        newtraj.f_load(name=trajectory_name, index=trajectory_index, as_new=as_new,
                       load_derived_parameters=2, load_results=2)
        return newtraj


    def explore(self,traj):
        self.explore_dict={'x':[0,1,2,3,4],'y':[1,1,2,2,3]}
        traj.f_explore(self.explore_dict)


    def expand(self,traj):
        self.expand_dict={'x':[10,11,12,13],'y':[11,11,12,12,13]}
        with self.assertRaises(ValueError):
            traj.f_expand(self.expand_dict)

        self.expand_dict={'x':[10,11,12,13],'y':[11,11,12,12]}
        traj.f_expand(self.expand_dict)


    def test_if_results_are_sorted_correctly(self):

        ###Explore
        self.explore(self.traj)


        self.env.f_run(multiply)
        traj = self.traj
        self.assertTrue(len(traj) == len(compat.listvalues(self.explore_dict)[0]))

        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj,newtraj)

    def test_f_iter_runs(self):

         ###Explore
        self.explore(self.traj)


        self.env.f_run(multiply)
        traj = self.traj
        self.assertTrue(len(traj) == len(compat.listvalues(self.explore_dict)[0]))

        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        for idx, run_name in enumerate(self.traj.f_iter_runs()):
            newtraj.v_as_run=run_name
            self.traj.v_as_run == run_name
            self.traj.v_idx = idx
            newtraj.v_idx = idx
            nameset = set((x.v_name for x in traj.f_iter_nodes(predicate=(idx,))))
            self.assertTrue('run_%08d' % (idx+1) not in nameset)
            self.assertTrue('run_%08d' % idx in nameset)
            self.assertTrue(traj.v_crun == run_name)
            self.assertTrue(newtraj.z==traj.x*traj.y,' z != x*y: %s != %s * %s' %
                                                  (str(newtraj.z),str(traj.x),str(traj.y)))

        self.assertTrue(traj.v_idx == -1)
        self.assertTrue(traj.v_crun is None)
        self.assertTrue(traj.v_crun_ == pypetconstants.RUN_NAME_DUMMY)
        self.assertTrue(newtraj.v_idx == idx)


    def test_expand(self):
        ###Explore
        self.explore(self.traj)

        logging.getLogger().info(self.env.f_run(multiply))
        traj = self.traj
        self.assertTrue(len(traj) == len(list(compat.listvalues(self.explore_dict)[0])))

        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        traj_name = self.env.v_trajectory.v_name
        del self.env
        self.env = Environment(trajectory=self.traj, log_folder=self.logfolder,
                          log_stdout=False, log_levels=get_log_level())

        self.traj = self.env.v_trajectory

        self.traj.f_load(name=traj_name)

        self.expand(self.traj)

        self.env.f_run(multiply)
        traj = self.traj
        self.assertTrue(len(traj) == len(compat.listvalues(self.expand_dict)[0])+ len(compat.listvalues(self.explore_dict)[0]))


        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj,newtraj)

    def test_expand_after_reload(self):
        ###Explore
        self.explore(self.traj)

        self.env.f_run(multiply)
        traj = self.traj
        self.assertTrue(len(traj) == len(compat.listvalues(self.explore_dict)[0]))

        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        self.expand(self.traj)

        self.env.f_run(multiply)
        traj = self.traj
        self.assertTrue(len(traj) == len(compat.listvalues(self.expand_dict)[0])+\
                        len(compat.listvalues(self.explore_dict)[0]))

        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj,newtraj)


    def check_if_z_is_correct(self,traj):
        for x in range(len(traj)):
            traj.v_idx=x

            self.assertTrue(traj.z==traj.x*traj.y,' z != x*y: %s != %s * %s' %
                                                  (str(traj.z),str(traj.x),str(traj.y)))
        traj.v_idx=-1


# def test_runfunc(traj, list_that_changes):
#     traj.f_add_result('kkk', list_that_changes[traj.v_idx] + traj.v_idx)
#     list_that_changes[traj.v_idx] = 1000

# class DeepCopyTest(TrajectoryComparator):
#
#     def test_deep_copy_data(self):
#
#         self.filename = make_temp_file('experiments/tests/HDF5/testcopy.hdf5')
#         self.logfolder = make_temp_file('experiments/tests/Log')
#         self.trajname = make_trajectory_name(self)
#
#         env = Environment(trajectory=self.trajname,filename=self.filename,
#                           file_title=self.trajname, log_folder=self.logfolder,
#                           log_stdout=False,
#                           multiproc=False,
#                           deep_copy_data=True)
#
#         traj = env.v_trajectory
#
#         traj.f_add_parameter('dummy', 1)
#         traj.f_explore({'dummy':[12, 3, 3, 4]})
#
#         list_that_should_not_change = [42, 42, 42, 42]
#
#         env.f_run(test_runfunc, list_that_should_not_change)
#
#         traj.v_auto_load=True
#
#         for irun, val in enumerate(list_that_should_not_change):
#             self.assertTrue(list_that_should_not_change[irun] == 42)
#             x=traj.results.runs[irun].kkk
#             self.assertTrue(x==42+irun)
#
#     def test_not_deep_copy_data(self):
#         self.filename = make_temp_file('experiments/tests/HDF5/testcoyp2.hdf5')
#         self.logfolder = make_temp_file('experiments/tests/Log')
#         self.trajname = make_trajectory_name(self)
#
#         env = Environment(trajectory=self.trajname,filename=self.filename,
#                           file_title=self.trajname, log_folder=self.logfolder,
#                           log_stdout=False,
#                           multiproc=False,
#                           deep_copy_data=False)
#
#         traj = env.v_trajectory
#
#         traj.f_add_parameter('dummy', 1)
#         traj.f_explore({'dummy':[12, 3, 3, 4]})
#
#         list_that_should_change = [42, 42, 42, 42]
#
#         env.f_run(test_runfunc, list_that_should_change)
#
#         traj.v_auto_load=True
#
#         for irun, val in enumerate(list_that_should_change):
#             self.assertTrue(list_that_should_change[irun] == 1000)



if __name__ == '__main__':
    run_suite()

