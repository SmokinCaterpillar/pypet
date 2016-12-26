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
from pypet import pypetconstants, Result, manual_run

import pypet.pypetexceptions as pex

import sys
import unittest

try:
    import psutil
except ImportError:
    psutil = None
try:
    import dill
except ImportError:
    dill = None

import scipy.sparse as spsp
import random
from pypet import Parameter

import tables as pt

from pypet.tests.testutils.ioutils import  run_suite, make_temp_dir,  make_trajectory_name,\
     get_root_logger, parse_args, get_log_config, get_log_path
from pypet.tests.testutils.data import create_param_dict, add_params, multiply,\
    simple_calculations, TrajectoryComparator, multiply_args, multiply_with_storing, \
    multiply_with_graceful_exit


def add_one_particular_item(traj, store_full):
    traj.hi = Result('hi', 42, 'hi!')
    traj.f_store()
    traj.f_remove_child('hi')


class SlowResult(Result):
    def _load(self, load_dict):
        time.sleep(3)
        super(SlowResult, self)._load(load_dict)


class FullStorageTest(TrajectoryComparator):

    tags = 'integration', 'hdf5', 'environment'  # Test tags

    def test_full_store(self):
        filename = make_temp_dir('full_store.hdf5')
        with Environment(filename=filename,
                         log_config=get_log_config()) as env:

            traj = env.v_trajectory

            traj.par.x = Parameter('x', 3, 'jj')

            traj.f_explore({'x': [1,2,3]})

            env.f_run(add_one_particular_item, True)

            traj = load_trajectory(index=-1, filename=filename)

            self.assertTrue('hi' in traj)


def with_niceness(traj):
    if traj.multiproc:
        if hasattr(os, 'nice'):
            trajnice = traj.niceness
            osnice = os.nice(0)
        else:
            trajnice = traj.niceness
            osnice = psutil.Process().nice()
        if trajnice != osnice:
            if traj.use_scoop:
                import scoop
                if (not scoop.IS_RUNNING or scoop.IS_ORIGIN):
                    return
            raise RuntimeError('traj niceness != os niceness; '
                               '%s != %s' % (str(trajnice), str(osnice)))


def add_large_data(traj):
    np_array = np.random.rand(100, 1000, 10)
    traj.f_add_result('l4rge', np_array)
    traj.f_store_item('l4rge')
    traj.f_remove_item('l4rge')

    array_list = []
    for irun in range(111):
        array_list.append(np.random.rand(10))
    traj.f_add_result('m4ny', *array_list)


class SimpleEnvironmentTest(TrajectoryComparator):

    tags = 'integration', 'hdf5', 'environment', 'quick'

    def test_make_default_file_when_giving_directory_without_slash(self):
        filename = make_temp_dir('test.hdf5')
        head, tail = os.path.split(filename)
        env = Environment(filename=head)
        the_file_name = env.v_traj.v_name + '.hdf5'
        head, tail = os.path.split(env.v_traj.v_storage_service.filename)
        self.assertEqual(tail, the_file_name)


class EnvironmentTest(TrajectoryComparator):

    tags = 'integration', 'hdf5', 'environment'

    def set_mode(self):
        self.mode = 'LOCK'
        self.multiproc = False
        self.gc_interval = None
        self.ncores = 1
        self.use_pool=True
        self.use_scoop=False
        self.freeze_input=False
        self.pandas_format='fixed'
        self.pandas_append=False
        self.complib = 'zlib'
        self.complevel=9
        self.shuffle=True
        self.fletcher32 = False
        self.encoding = 'utf8'
        self.log_stdout=False
        self.wildcard_functions = None
        self.niceness = None
        self.port = None
        self.timeout = None
        self.add_time=True
        self.graceful_exit = False

    def explore_complex_params(self, traj):
        matrices_csr = []
        for irun in range(3):

            spsparse_csr = spsp.lil_matrix((111,111))
            spsparse_csr[3,2+irun] = 44.5*irun

            matrices_csr.append(spsparse_csr.tocsr())

        matrices_csc = []
        for irun in range(3):

            spsparse_csc = spsp.lil_matrix((111,111))
            spsparse_csc[3,2+irun] = 44.5*irun

            matrices_csc.append(spsparse_csc.tocsc())

        matrices_bsr = []
        for irun in range(3):

            spsparse_bsr = spsp.lil_matrix((111,111))
            spsparse_bsr[3,2+irun] = 44.5*irun

            matrices_bsr.append(spsparse_bsr.tocsr().tobsr())

        matrices_dia = []
        for irun in range(3):

            spsparse_dia = spsp.lil_matrix((111,111))
            spsparse_dia[3,2+irun] = 44.5*irun

            matrices_dia.append(spsparse_dia.tocsc().todia())


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
            'csr_mat' :[spsp.lil_matrix((2222,22)), spsp.lil_matrix((2222,22))]}

        self.explored['csr_mat'][0][1,2]=44.0
        self.explored['csr_mat'][1][2,2]=33

        self.explored['csr_mat'][0] = self.explored['csr_mat'][0].tocsr()
        self.explored['csr_mat'][1] = self.explored['csr_mat'][0].tocsr()

        traj.f_explore(cartesian_product(self.explored))

    def explore_large(self, traj):
        self.explored ={'Normal.trial': [0,1]}
        traj.f_explore(cartesian_product(self.explored))

    def tearDown(self):
        self.env.f_disable_logging()

        super(EnvironmentTest, self).tearDown()

    def setUp(self):
        self.set_mode()
        self.logfolder = make_temp_dir(os.path.join('experiments',
                                                      'tests',
                                                      'Log'))

        random.seed()
        self.trajname = make_trajectory_name(self)
        self.filename = make_temp_dir(os.path.join('experiments',
                                                    'tests',
                                                    'HDF5',
                                                    'test%s.hdf5' % self.trajname))

        env = Environment(trajectory=self.trajname, filename=self.filename,
                          file_title=self.trajname,
                          log_stdout=self.log_stdout,
                          log_config=get_log_config(),
                          results_per_run=5,
                          wildcard_functions=self.wildcard_functions,
                          derived_parameters_per_run=5,
                          multiproc=self.multiproc,
                          ncores=self.ncores,
                          wrap_mode=self.mode,
                          use_pool=self.use_pool,
                          gc_interval=self.gc_interval,
                          freeze_input=self.freeze_input,
                          fletcher32=self.fletcher32,
                          complevel=self.complevel,
                          complib=self.complib,
                          shuffle=self.shuffle,
                          pandas_append=self.pandas_append,
                          pandas_format=self.pandas_format,
                          encoding=self.encoding,
                          niceness=self.niceness,
                          use_scoop=self.use_scoop,
                          port=self.port,
                          add_time=self.add_time,
                          timeout=self.timeout,
                          graceful_exit=self.graceful_exit)

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

    @unittest.skipIf(not hasattr(os, 'nice') and psutil is None, 'Niceness not supported under non Unix.')
    def test_niceness(self):
        ###Explore
        self.explore(self.traj)

        self.env.f_run(with_niceness)

        self.assertTrue(self.traj.f_is_completed())

    def test_file_overwriting(self):
        self.traj.f_store()

        with pt.open_file(self.filename, mode='r') as file:
            nchildren = len(file.root._v_children)
            self.assertTrue(nchildren > 0)

        env2 = Environment(filename=self.filename,
                           log_config=get_log_config())
        traj2 = env2.v_trajectory
        traj2.f_store()

        self.assertTrue(os.path.exists(self.filename))

        with pt.open_file(self.filename, mode='r') as file:
            nchildren = len(file.root._v_children)
            self.assertTrue(nchildren > 1)

        env3 = Environment(filename=self.filename, overwrite_file=True,
                           log_config=get_log_config())

        self.assertFalse(os.path.exists(self.filename))

        env2.f_disable_logging()
        env3.f_disable_logging()

    def test_time_display_of_loading(self):
        filename = make_temp_dir('sloooow.hdf5')
        env = Environment(trajectory='traj', add_time=True, filename=filename,
                          log_stdout=False,
                          log_config=get_log_config(),
                          dynamic_imports=SlowResult,
                          display_time=0.1)
        traj = env.v_traj
        res=traj.f_add_result(SlowResult, 'iii', 42, 43, comment='llk')
        traj.f_store()
        service_logger = traj.v_storage_service._logger
        root = logging.getLogger('pypet')
        old_level = root.level
        service_logger.setLevel(logging.INFO)
        root.setLevel(logging.INFO)

        traj.f_load(load_data=3)
        service_logger.setLevel(old_level)
        root.setLevel(old_level)

        path = get_log_path(traj)
        mainfilename = os.path.join(path, 'LOG.txt')
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
        results =  self.env.f_run(simple_calculations,simple_arg,simple_kwarg=simple_kwarg)
        self.are_results_in_order(results)

    def test_a_large_run(self):
        get_root_logger().info('Testing large run')
        self.traj.f_add_parameter('TEST', 'test_run')
        ###Explore
        self.explore_large(self.traj)
        self.make_run_large_data()

        self.assertTrue(self.traj.f_is_completed())

        # Check if printing and repr work
        get_root_logger().info(str(self.env))
        get_root_logger().info(repr(self.env))

        newtraj = Trajectory()
        newtraj.f_load(name=self.traj.v_name, as_new=False, load_data=2, filename=self.filename)

        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj,newtraj)

        size=os.path.getsize(self.filename)
        size_in_mb = size/1000000.
        get_root_logger().info('Size is %sMB' % str(size_in_mb))
        self.assertTrue(size_in_mb < 30.0, 'Size is %sMB > 30MB' % str(size_in_mb))

    def test_two_runs(self):
        self.traj.f_add_parameter('TEST', 'test_run')
        self.traj.hdf5.purge_duplicate_comments = False
        ###Explore
        self.explore(self.traj)

        self.make_run()

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj, newtraj)

        size=os.path.getsize(self.filename)
        size_in_mb = size/1000000.
        get_root_logger().info('Size is %sMB' % str(size_in_mb))
        self.assertTrue(size_in_mb < 6.0, 'Size is %sMB > 6MB' % str(size_in_mb))

        mp_traj = self.traj

        old_multiproc = self.multiproc
        self.multiproc = False

        ### Make a new single core run
        self.setUp()

        self.traj.f_add_parameter('TEST', 'test_run')
        self.traj.hdf5.purge_duplicate_comments = False
        ###Explore
        self.explore(self.traj)

        self.make_run()

        # newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj, newtraj)

        size=os.path.getsize(self.filename)
        size_in_mb = size/1000000.
        get_root_logger().info('Size is %sMB' % str(size_in_mb))
        self.assertTrue(size_in_mb < 6.0, 'Size is %sMB > 6MB' % str(size_in_mb))

        self.compare_trajectories(mp_traj, self.traj)
        self.multiproc = old_multiproc

    def test_errors(self):
        tmp = make_temp_dir('cont')
        if dill is not None:
            env1 = Environment(continuable=True, continue_folder=tmp,
                           log_config=None, filename=self.filename)
            with self.assertRaises(ValueError):
                env1.f_run_map(multiply_args, [1], [2], [3])
        with self.assertRaises(ValueError):
            Environment(multiproc=True, use_pool=False, freeze_input=True,
                           filename=self.filename, log_config=None)
        env3 = Environment(log_config=None, filename=self.filename)
        with self.assertRaises(ValueError):
            env3.f_run_map(multiply_args)
        with self.assertRaises(ValueError):
            Environment(use_scoop=True, immediate_postproc=True)
        with self.assertRaises(ValueError):
            Environment(use_pool=True, immediate_postproc=True)
        with self.assertRaises(ValueError):
            Environment(continuable=True, wrap_mode='QUEUE', continue_folder=tmp)
        with self.assertRaises(ValueError):
            Environment(use_scoop=True, wrap_mode='QUEUE')
        with self.assertRaises(ValueError):
            Environment(automatic_storing=False,
                        continuable=True, continue_folder=tmp)
        with self.assertRaises(ValueError):
            Environment(port='www.nosi.de', wrap_mode='LOCK')

    def test_run(self):
        self.traj.f_add_parameter('TEST', 'test_run')
        ###Explore
        self.explore(self.traj)

        self.make_run()

        self.assertTrue(self.traj.f_is_completed())

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj, newtraj)

        size=os.path.getsize(self.filename)
        size_in_mb = size/1000000.
        get_root_logger().info('Size is %sMB' % str(size_in_mb))
        self.assertTrue(size_in_mb < 6.0, 'Size is %sMB > 6MB' % str(size_in_mb))

    def test_just_one_run(self):
        self.make_run()
        self.assertTrue(self.traj.f_is_completed())

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj, newtraj)

        self.assertTrue(len(newtraj) == 1)

        size=os.path.getsize(self.filename)
        size_in_mb = size/1000000.
        get_root_logger().info('Size is %sMB' % str(size_in_mb))
        self.assertTrue(size_in_mb < 2.0, 'Size is %sMB > 6MB' % str(size_in_mb))

        with self.assertRaises(TypeError):
            self.explore(self.traj)

    def test_run_complex(self):
        self.traj.f_add_parameter('TEST', 'test_run_complex')
        ###Explore
        self.explore_complex_params(self.traj)

        self.make_run()

        self.assertTrue(self.traj.f_is_completed())

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
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

        get_root_logger().info('\n $$$$$$$$$$$$$$$$$ Second Run $$$$$$$$$$$$$$$$$$$$$$$$')
        self.make_run()

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj, newtraj)

    def test_expand_after_reload(self):

        self.traj.f_add_parameter('TEST', 'test_expand_after_reload')
        ###Explore
        self.explore(self.traj)

        self.make_run()

        traj_name = self.traj.v_name


        self.env = Environment(trajectory=self.traj,
                          log_stdout=False,
                          log_config=get_log_config())

        self.traj = self.env.v_trajectory

        self.traj.f_load(name=traj_name)
        self.traj.res.f_remove()
        self.traj.dpar.f_remove()

        self.expand()

        get_root_logger().info('\n $$$$$$$$$$$$ Second Run $$$$$$$$$$ \n')
        self.make_run()

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj, newtraj)


    def expand(self):
        self.expanded ={'Normal.trial': [1],
            'Numpy.double': [np.array([1.0,2.0,3.0,4.0]), np.array([-1.0,3.0,5.0,7.0])],
            'csr_mat' :[spsp.lil_matrix((2222,22)), spsp.lil_matrix((2222,22))]}

        self.expanded['csr_mat'][0][1,2]=44.0
        self.expanded['csr_mat'][1][2,2]=33
        self.expanded['csr_mat'][0]=self.expanded['csr_mat'][0].tocsr()
        self.expanded['csr_mat'][1]=self.expanded['csr_mat'][1].tocsr()

        self.traj.f_expand(cartesian_product(self.expanded))
        self.traj.f_store()


    ################## Overview TESTS #############################

    def test_switch_ON_large_tables(self):
        self.traj.f_add_parameter('TEST', 'test_switch_ON_LARGE_tables')
        ###Explore
        self.explore(self.traj)

        self.env._traj.config.hdf5.overview.results_overview = 1
        self.env._traj.config.hdf5.overview.derived_parameters_overview = 1
        self.make_run()

        hdf5file = pt.open_file(self.filename)
        overview_group = hdf5file.get_node(where='/'+ self.traj.v_name, name='overview')
        should = ['derived_parameters_overview', 'results_overview']
        for name in should:
            self.assertTrue(name in overview_group, '%s not in overviews but it should!' % name)
        hdf5file.close()

        self.traj.f_load(load_parameters=2, load_derived_parameters=2, load_results=2)
        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name)

        self.compare_trajectories(newtraj,self.traj)

    def test_switch_off_all_tables(self):
        ###Explore
        self.traj.f_add_parameter('TEST', 'test_switch_off_ALL_tables')
        self.explore(self.traj)

        self.env._traj.config.hdf5.overview.results_overview = 0
        self.env._traj.config.hdf5.overview.derived_parameters_overview = 0
        self.env._traj.config.hdf5.overview.derived_parameters_summary = 0
        self.env._traj.config.hdf5.overview.results_summary = 0
        self.env._traj.config.hdf5.purge_duplicate_comments = 0
        self.env._traj.config.hdf5.overview.parameters_overview = 0
        self.env._traj.config.hdf5.overview.config_overview = 0
        self.env._traj.config.hdf5.overview.explored_parameters_overview = 0
        self.make_run()

        hdf5file = pt.open_file(self.filename)
        overview_group = hdf5file.get_node(where='/'+ self.traj.v_name, name='overview')
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

        hdf5file = pt.open_file(self.filename)
        traj_group = hdf5file.get_node(where='/', name= self.traj.v_name)

        for node in traj_group._f_walk_groups():
            if 'SRVC_LEAF' in node._v_attrs:
                self.assertTrue('SRVC_INIT_COMMENT' in node._v_attrs,
                                    'There is no comment in node %s!' % node._v_name)

        hdf5file.close()


    def test_purge_duplicate_comments(self):
        self.explore(self.traj)

        with self.assertRaises(RuntimeError):
            self.traj.hdf5.purge_duplicate_comments = 1
            self.traj.overview.results_summary = 0
            self.make_run()

        self.traj.f_get('purge_duplicate_comments').f_unlock()
        self.traj.hdf5.purge_duplicate_comments=1
        self.traj.f_get('results_summary').f_unlock()
        self.traj.overview.results_summary=1
        self.make_run()


        hdf5file = pt.open_file(self.filename, mode='a')

        ncomments = {}

        try:
            traj_group = hdf5file.get_node(where='/',name= self.traj.v_name)


            for node in traj_group._f_walk_groups():
                if ('/derived_parameters/' in node._v_pathname or
                    '/results/' in node._v_pathname):
                    if 'SRVC_LEAF' in node._v_attrs:
                        if 'SRVC_INIT_COMMENT' in node._v_attrs:
                            comment = node._v_attrs['SRVC_INIT_COMMENT']
                            if comment not in ncomments:
                                ncomments[comment] = 0
                            ncomments[comment] += 1
        finally:
            hdf5file.close()

        self.assertGreaterEqual(len(ncomments), 1)
        self.assertTrue(all(x == 1 for x in ncomments.values()))

    def test_NOT_purge_duplicate_comments(self):
        self.explore(self.traj)
        self.traj.f_get('purge_duplicate_comments').f_unlock()
        self.traj.hdf5.purge_duplicate_comments=0
        self.traj.f_get('results_summary').f_unlock()
        self.traj.overview.results_summary=0
        self.make_run()

        hdf5file = pt.open_file(self.filename, mode='a')

        ncomments = {}

        try:
            traj_group = hdf5file.get_node(where='/',name= self.traj.v_name)


            for node in traj_group._f_walk_groups():
                if ('/derived_parameters/' in node._v_pathname or
                    '/results/' in node._v_pathname):
                    if 'SRVC_LEAF' in node._v_attrs:
                        if 'SRVC_INIT_COMMENT' in node._v_attrs:
                            comment = node._v_attrs['SRVC_INIT_COMMENT']
                            if comment not in ncomments:
                                ncomments[comment] = 0
                            ncomments[comment] += 1
        finally:
            hdf5file.close()

        self.assertGreaterEqual(len(ncomments), 1)
        self.assertTrue(any(x > 1 for x in ncomments.values()))


def my_run_func(idx):
    return 'hello_%d' % idx

def my_set_func(idx):
    return 'huhu_%d' % idx

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
        self.complib = 'blosc'
        self.complevel=2
        self.shuffle=False
        self.fletcher32 = False
        self.encoding='latin1'
        self.graceful_exit = True



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
        self.wildcard_functions = {('$', 'crun') : my_run_func, ('$set', 'crunset'): my_set_func}


class ResultSortTest(TrajectoryComparator):

    tags = 'integration', 'hdf5', 'environment'

    def set_mode(self):
        self.mode = 'LOCK'
        self.multiproc = False
        self.ncores = 1
        self.use_pool=True
        self.log_stdout=False
        self.freeze_input=False
        self.use_scoop = False
        self.log_config = True
        self.port = None
        self.graceful_exit = True

    def tearDown(self):
        self.env.f_disable_logging()
        super(ResultSortTest, self).tearDown()

    def setUp(self):
        self.set_mode()

        self.filename = make_temp_dir(os.path.join('experiments','tests','HDF5','sort_tests.hdf5'))

        self.trajname = make_trajectory_name(self)

        env = Environment(trajectory=self.trajname,filename=self.filename,
                          file_title=self.trajname,
                          log_stdout=self.log_stdout,
                          log_config=get_log_config() if self.log_config else None,
                          multiproc=self.multiproc,
                          wrap_mode=self.mode,
                          ncores=self.ncores,
                          use_pool=self.use_pool,
                          use_scoop=self.use_scoop,
                          port=self.port,
                          freeze_input=self.freeze_input,
                          graceful_exit=self.graceful_exit)

        traj = env.v_trajectory


        traj.v_standard_parameter=Parameter

        traj.f_add_parameter('x',99)
        traj.f_add_parameter('y',99)

        self.env=env
        self.traj=traj

    def load_trajectory(self,trajectory_index=None,trajectory_name=None,as_new=False, how=2):
        ### Load The Trajectory and check if the values are still the same
        newtraj = Trajectory()
        newtraj.v_storage_service=HDF5StorageService(filename=self.filename)
        newtraj.f_load(name=trajectory_name, index=trajectory_index, as_new=as_new,
                       load_derived_parameters=how, load_results=how)
        return newtraj


    def explore(self,traj):
        self.explore_dict={'x':[-1,1,2,3,4],'y':[1,1,2,2,3]}
        traj.f_explore(self.explore_dict)

    def explore_cartesian(self,traj):
        self.explore_dict=cartesian_product({'x':[-1,1,2,3,4, 5, 6],'y':[1,1,2,2,3,4,4]})
        traj.f_explore(self.explore_dict)

    def expand(self,traj):
        self.expand_dict={'x':[10,11,12,13],'y':[11,11,12,12,13]}
        with self.assertRaises(ValueError):
            traj.f_expand(self.expand_dict)

        self.expand_dict={'x':[10,11,12,13],'y':[11,11,12,12]}
        traj.f_expand(self.expand_dict)

    def test_if_results_are_sorted_correctly_manual_runs(self):
        ###Explore
        self.explore(self.traj)
        self.traj.f_store(only_init=True)
        man_multiply = manual_run()(multiply_with_storing)
        for idx in self.traj.f_iter_runs(yields='idx'):
            self.assertTrue(isinstance(idx, int))
            man_multiply(self.traj)
        traj = self.traj
        traj.f_store()
        self.assertTrue(len(traj), 5)
        self.assertTrue(len(traj) == len(list(self.explore_dict.values())[0]))

        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj,newtraj)

    def test_if_results_are_sorted_correctly_using_map(self):
        ###Explore
        self.explore(self.traj)

        args1=[10*x for x in range(len(self.traj))]
        args2=[100*x for x in range(len(self.traj))]
        args3=list(range(len(self.traj)))

        results = self.env.f_run_map(multiply_args, args1, arg2=args2, arg3=args3)
        self.assertEqual(len(results), len(self.traj))

        traj = self.traj
        self.assertTrue(len(traj) == len(list(self.explore_dict.values())[0]))

        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct_map(traj, args1, args2, args3)

        for res in results:
            self.assertEqual(len(res), 2)
            self.assertTrue(isinstance(res[0], int))
            self.assertTrue(isinstance(res[1], int))
            idx = res[0]
            self.assertEqual(self.traj.res.runs[idx].z, res[1])

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.assertEqual(len(traj), 5)
        self.compare_trajectories(self.traj,newtraj)

    def test_if_results_are_sorted_correctly(self):

        ###Explore
        self.explore(self.traj)

        results = self.env.f_run(multiply)
        self.are_results_in_order(results)
        self.assertEqual(len(results), len(self.traj))


        traj = self.traj
        self.assertTrue(len(traj) == len(list(self.explore_dict.values())[0]))

        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        for res in results:
            self.assertEqual(len(res), 2)
            self.assertTrue(isinstance(res[0], int))
            self.assertTrue(isinstance(res[1], int))
            idx = res[0]
            self.assertEqual(self.traj.res.runs[idx].z, res[1])

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj,newtraj)

    def test_graceful_exit(self):

        ###Explore
        self.explore_cartesian(self.traj)

        results = self.env.f_run(multiply_with_graceful_exit)
        self.are_results_in_order(results)
        self.assertFalse(self.traj.f_is_completed())

    def test_f_iter_runs(self):

         ###Explore
        self.explore(self.traj)


        results = self.env.f_run(multiply)
        self.are_results_in_order(results)
        traj = self.traj
        self.assertTrue(len(traj) == len(list(self.explore_dict.values())[0]))

        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        for idx, run_name in enumerate(self.traj.f_iter_runs()):
            newtraj.v_crun=run_name
            self.traj.v_idx = idx
            newtraj.v_idx = idx
            nameset = set((x.v_name for x in traj.f_iter_nodes(predicate=(idx,))))
            self.assertTrue('run_%08d' % (idx+1) not in nameset)
            self.assertTrue('run_%08d' % idx in nameset)
            self.assertTrue(traj.v_crun == run_name)
            self.assertTrue(newtraj.crun.z==traj.x*traj.y,' z != x*y: %s != %s * %s' %
                                                  (str(newtraj.crun.z),str(traj.x),str(traj.y)))

        for idx, traj in enumerate(self.traj.f_iter_runs(yields='self')):
            run_name = traj.f_idx_to_run(idx)
            self.assertTrue(traj is self.traj)
            newtraj.v_crun=run_name
            self.traj.v_idx = idx
            newtraj.v_idx = idx
            nameset = set((x.v_name for x in traj.f_iter_nodes(predicate=(idx,))))
            self.assertTrue('run_%08d' % (idx+1) not in nameset)
            self.assertTrue('run_%08d' % idx in nameset)
            self.assertTrue(traj.v_crun == run_name)
            self.assertTrue(newtraj.crun.z==traj.x*traj.y,' z != x*y: %s != %s * %s' %
                                                  (str(newtraj.crun.z),str(traj.x),str(traj.y)))

        for idx, traj in enumerate(self.traj.f_iter_runs(yields='copy')):
            run_name = traj.f_idx_to_run(idx)
            self.assertTrue(traj is not self.traj)
            newtraj.v_crun=run_name
            self.traj.v_idx = idx
            newtraj.v_idx = idx
            nameset = set((x.v_name for x in traj.f_iter_nodes(predicate=(idx,))))
            self.assertTrue('run_%08d' % (idx+1) not in nameset)
            self.assertTrue('run_%08d' % idx in nameset)
            self.assertTrue(traj.v_crun == run_name)
            self.assertTrue(newtraj.crun.z==traj.x*traj.y,' z != x*y: %s != %s * %s' %
                                                  (str(newtraj.crun.z),str(traj.x),str(traj.y)))

        traj = self.traj
        self.assertTrue(traj.v_idx == -1)
        self.assertTrue(traj.v_crun is None)
        self.assertTrue(traj.v_crun_ == pypetconstants.RUN_NAME_DUMMY)
        self.assertTrue(newtraj.v_idx == idx)


    def test_f_iter_runs_auto_load(self):

         ###Explore
        self.explore(self.traj)

        results = self.env.f_run(multiply)
        self.are_results_in_order(results)
        traj = self.traj
        self.assertTrue(len(traj) == len(list(self.explore_dict.values())[0]))

        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        newtraj = Trajectory()
        newtraj.v_storage_service=HDF5StorageService(filename=self.filename)
        newtraj.f_load(name=self.traj.v_name, index=None, as_new=False, load_data=0)
        newtraj.v_auto_load = True

        newtraj.par.f_load_child('y', load_data=1)

        for idx, run_name in enumerate(self.traj.f_iter_runs()):
            newtraj.v_crun=run_name
            self.traj.v_idx = idx
            newtraj.v_idx = idx
            nameset = set((x.v_name for x in traj.f_iter_nodes(predicate=(idx,))))
            self.assertTrue('run_%08d' % (idx+1) not in nameset)
            self.assertTrue('run_%08d' % idx in nameset)
            self.assertTrue(traj.v_crun == run_name)
            self.assertTrue(newtraj.res.runs.crun.z==newtraj.par.x*newtraj.par.y,' z != x*y: %s != %s * %s' %
                                                  (str(newtraj.crun.z),str(newtraj.x),str(newtraj.y)))


        traj = self.traj
        self.assertTrue(traj.v_idx == -1)
        self.assertTrue(traj.v_crun is None)
        self.assertTrue(traj.v_crun_ == pypetconstants.RUN_NAME_DUMMY)
        self.assertTrue(newtraj.v_idx == idx)



    def test_expand(self):
        ###Explore
        self.explore(self.traj)

        results = self.env.f_run(multiply)
        self.are_results_in_order(results)

        get_root_logger().info(results)
        traj = self.traj
        self.assertEqual(len(traj), len(list(list(self.explore_dict.values())[0])))

        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        traj_name = self.env.v_trajectory.v_name
        del self.env
        self.env = Environment(trajectory=self.traj,
                          log_stdout=False,
                          log_config=get_log_config())

        self.traj = self.env.v_trajectory

        self.traj.f_load(name=traj_name)

        self.expand(self.traj)

        results = self.env.f_run(multiply)
        self.are_results_in_order(results)

        traj = self.traj
        self.assertTrue(len(traj) == len(list(self.expand_dict.values())[0])+
                        len(list(self.explore_dict.values())[0]))


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

        results = self.env.f_run(multiply)
        self.are_results_in_order(results)

        traj = self.traj
        self.assertTrue(len(traj) == len(list(self.explore_dict.values())[0]))

        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        self.expand(self.traj)

        self.env.f_run(multiply)
        traj = self.traj
        self.assertTrue(len(traj) == len(list(self.expand_dict.values())[0])+\
                        len(list(self.explore_dict.values())[0]))

        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj,newtraj)

    def check_if_z_is_correct_map(self,traj, args1, args2, args3):
        for x, arg1, arg2, arg3 in zip(range(len(traj)), args1, args2, args3):
            traj.v_idx=x
            self.assertTrue(traj.crun.z==traj.x*traj.y+arg1+arg2+arg3,' z != x*y: %s != %s * %s' %
                                                  (str(traj.crun.z),str(traj.x),str(traj.y)))
        traj.v_idx=-1

    def check_if_z_is_correct(self,traj):
        traj.v_shortcuts=False
        for x in range(len(traj)):
            traj.v_idx=x
            z = traj.res.runs.crun.z
            x = traj.par.x
            y = traj.par.y
            self.assertTrue(z==x*y,' z != x*y: %s != %s * %s' %
                                                  (str(z),str(x),str(y)))
        traj.v_idx=-1
        traj.v_shortcuts=True


# def test_runfunc(traj, list_that_changes):
#     traj.f_add_result('kkk', list_that_changes[traj.v_idx] + traj.v_idx)
#     list_that_changes[traj.v_idx] = 1000

# class DeepCopyTest(TrajectoryComparator):
#
#     def test_deep_copy_data(self):
#
#         self.filename = make_temp_dir('experiments/tests/HDF5/testcopy.hdf5')
#         self.logfolder = make_temp_dir('experiments/tests/Log')
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
#         self.filename = make_temp_dir('experiments/tests/HDF5/testcoyp2.hdf5')
#         self.logfolder = make_temp_dir('experiments/tests/Log')
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
    opt_args = parse_args()
    run_suite(**opt_args)
