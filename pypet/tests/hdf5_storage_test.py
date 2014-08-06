

__author__ = 'Robert Meyer'

import numpy as np
from pypet.parameter import Parameter, PickleParameter, ArrayParameter, PickleResult
from pypet.trajectory import Trajectory
from pypet.utils.explore import cartesian_product
from pypet.environment import Environment
from pypet.storageservice import HDF5StorageService
from pypet import pypetconstants, BaseParameter, BaseResult
import logging
import pypet.pypetexceptions as pex

import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

import scipy.sparse as spsp
import random
import tables
import inspect
import pypet.compat as compat

import tables as pt

from pypet.tests.test_helpers import add_params, create_param_dict, simple_calculations, make_run,\
    make_temp_file, TrajectoryComparator, multiply, make_trajectory_name



class StorageTest(TrajectoryComparator):

    def test_storage_service_errors(self):

        traj = Trajectory(filename=make_temp_file('testnoservice.hdf5'))

        traj_name = traj.v_name

        # you cannot store stuff before the trajectory was stored once:
        with self.assertRaises(ValueError):
            traj.v_storage_service.store('FAKESERVICE', self, trajectory_name = traj.v_name)


        traj.f_store()

        with self.assertRaises(ValueError):
            traj.v_storage_service.store('FAKESERVICE', self, trajectory_name = 'test')

        with self.assertRaises(pex.NoSuchServiceError):
            traj.v_storage_service.store('FAKESERVICE', self, trajectory_name = traj.v_name)

        with self.assertRaises(ValueError):
            traj.f_load(name = 'test', index=1)

        with self.assertRaises(RuntimeError):
            traj.v_storage_service.store('LIST', [('LEAF',None,None,None,None)], trajectory_name = traj.v_name)

        with self.assertRaises(ValueError):
            traj.f_load(index=9999)

        with self.assertRaises(ValueError):
            traj.f_load(name='Non-Existising-Traj')


    def test_migrations(self):

        traj = Trajectory(name='Test', filename=make_temp_file('migrate.hdf5'))

        traj.f_add_result('I.am.a.mean.resu', 42, comment='Test')
        traj.f_add_derived_parameter('ffa', 42)

        traj.f_store()

        new_file = make_temp_file('migrate2.hdf5')
        traj.f_migrate(new_filename=new_file)

        traj.f_store()

        new_traj = Trajectory()

        new_traj.f_migrate(new_name=traj.v_name, new_filename=new_file, in_store=True)

        new_traj.v_auto_load=True

        self.assertTrue(new_traj.results.I.am.a.mean.resu == 42)

    def test_wildcard_search(self):

        traj = Trajectory(name='Test', filename=make_temp_file('wilcard.hdf5'))

        traj.f_add_parameter('expl', 2)
        traj.f_explore({'expl':[1,2,3,4]})

        traj.f_add_result('wc2test.$.hhh', 333)
        traj.f_add_leaf('results.wctest.run_00000000.jjj', 42)
        traj.f_add_result('results.wctest.run_00000001.jjj', 43)

        traj.v_as_run = 1

        self.assertTrue(traj.results.wctest['$'].jjj==43)
        self.assertTrue(traj.results.wc2test.crun.hhh==333)

        traj.f_store()

        traj.f_remove_child('results', recursive=True)

        traj.v_auto_load = True

        self.assertTrue(traj.results.wctest['$'].jjj==43)
        self.assertTrue(traj.results.wc2test.crun.hhh==333)

        traj.f_remove_child('results', recursive=True)

        traj.v_auto_load = True

        self.assertTrue(traj.results.wctest[-2].jjj==43)
        self.assertTrue(traj.results.wc2test[-2].hhh==333)

        traj.f_remove_child('results', recursive=True)

        traj.v_auto_load = True

        self.assertTrue(traj.results.wctest[1].jjj==43)
        self.assertTrue(traj.results.wc2test[-1].hhh==333)

    def test_store_and_load_large_dictionary(self):
        traj = Trajectory(name='Test', filename=make_temp_file('large_dict.hdf5'))

        large_dict = {}

        for irun in range(1025):
            large_dict['item_%d' % irun] = irun

        large_dict2 = {}

        for irun in range(33):
            large_dict2['item_%d' % irun] = irun

        traj.f_add_result('large_dict', large_dict, comment='Huge_dict!')
        traj.f_add_result('large_dict2', large_dict2, comment='Not so large dict!')

        traj.f_store()

        traj_name = traj.v_name

        traj2 = Trajectory(filename=make_temp_file('large_dict.hdf5'))

        traj2.f_load(name=traj_name, load_all=2)

        self.compare_trajectories(traj, traj2)


    def test_auto_load(self):


        traj = Trajectory(name='Test', filename=make_temp_file('autoload.hdf5'))

        traj.v_auto_load = True

        traj.f_add_result('I.am.$.a.mean.resu', 42, comment='Test')

        traj.f_add_derived_parameter('ffa', 42)

        traj.f_store()

        ffa=traj.f_get('ffa')
        ffa.f_unlock()
        ffa.f_empty()

        self.assertTrue(ffa.f_is_empty())

        traj.f_remove_child('results', recursive=True)

        # check auto load
        val = traj.res.I.am.crun.a.mean.resu

        self.assertTrue(val==42)

        val = traj.ffa

        self.assertTrue(val==42)

        with self.assertRaises(Exception):
            traj.kdsfdsf


    def test_version_mismatch(self):
        traj = Trajectory(name='Test', filename=make_temp_file('testversionmismatch.hdf5'))

        traj.f_add_parameter('group1.test',42)

        traj.f_add_result('testres', 42)

        traj.group1.f_set_annotations(Test=44)

        traj._version='0.1a.1'

        traj.f_store()



        traj2 = Trajectory(name=traj.v_name, add_time=False,
                           filename=make_temp_file('testversionmismatch.hdf5'))

        with self.assertRaises(pex.VersionMismatchError):
            traj2.f_load(load_results=2,load_parameters=2)

        traj2.f_load(load_results=2,load_parameters=2, force=True)

        self.compare_trajectories(traj,traj2)


    def test_partially_delete_stuff(self):
        traj = Trajectory(name='TestDelete',
                          filename=make_temp_file('testpartiallydel.hdf5'))

        res = traj.f_add_result('mytest.test', a='b', c='d')

        traj.f_store()

        self.assertTrue('a' in res)
        traj.f_delete_item(res, delete_only=['a'], remove_from_item=True)

        self.assertTrue('c' in res)
        self.assertTrue('a' not in res)

        res['a'] = 'offf'

        self.assertTrue('a' in res)

        traj.f_load(load_results=3)

        self.assertTrue('a' not in res)
        self.assertTrue('c' in res)

        traj.f_delete_item(res, remove_from_trajectory=True, remove_empty_groups=True)

        self.assertTrue('results' not in traj)
        self.assertTrue(res not in traj)

    def test_overwrite_stuff(self):
        traj = Trajectory(name='Test', filename=make_temp_file('testowrite.hdf5'))

        res = traj.f_add_result('mytest.test', a='b', c='d')

        traj.f_store()

        res['a'] = 333
        res['c'] = 123445

        traj.f_store_item(res, overwrite='a')

        # Should emit a warning
        traj.f_store_item(res, overwrite=['a', 'b'])

        traj.f_load(load_results=3)

        res = traj.test

        self.assertTrue(res['a']==333)
        self.assertTrue(res['c']=='d')

        res['c'] = 123445

        traj.f_store_item(res, overwrite=True)
        res.f_empty()

        traj.f_load(load_results=3)

        self.assertTrue(traj.test['c']==123445)



    def test_partial_loading(self):
        traj = Trajectory(name='TestPartial', filename=make_temp_file('testpartially.hdf5'))

        res = traj.f_add_result('mytest.test', a='b', c='d')

        traj.f_store()

        traj.f_remove_child('results', recursive=True)

        traj.f_update_skeleton()

        traj.f_load_item(traj.test, load_only=['a', 'x'])

        self.assertTrue('a' in traj.test)
        self.assertTrue('c' not in traj.test)

        traj.f_remove_child('results', recursive=True)

        traj.f_update_skeleton()

        load_except= ['c', 'd']
        traj.f_load_item(traj.test, load_except=load_except)

        self.assertTrue(len(load_except)==2)

        self.assertTrue('a' in traj.test)
        self.assertTrue('c' not in traj.test)

        with self.assertRaises(ValueError):
            traj.f_load_item(traj.test, load_except=['x'], load_only=['y'])


    def test_hdf5_settings(self):

        filename = make_temp_file('hdfsettings.hdf5')
        env = Environment('testraj', filename=filename,
                          add_time=True,
                         comment='',
                         dynamically_imported_classes=None,
                         log_folder=None,
                         log_level=None,
                         log_stdout=False,
                         multiproc=False,
                         ncores=3,
                         wrap_mode=pypetconstants.WRAP_MODE_LOCK,
                         continuable=False,
                         use_hdf5=True,
                         complevel=4,
                         complib='zlib',
                         shuffle=True,
                         fletcher32=True,
                         pandas_format='t',
                         pandas_append=True,
                         purge_duplicate_comments=True,
                         summary_tables=True,
                         small_overview_tables=True,
                         large_overview_tables=True,
                         results_per_run=19,
                         derived_parameters_per_run=17)

        traj = env.v_trajectory

        traj.f_store()

        hdf5file = pt.openFile(filename=filename)

        table= hdf5file.root._f_getChild(traj.v_name)._f_getChild('overview')._f_getChild('hdf5_settings')

        row = table[0]

        self.assertTrue(row['complevel'] == 4)

        self.assertTrue(row['complib'] == compat.tobytetype('zlib'))

        self.assertTrue(row['shuffle'])
        self.assertTrue(row['fletcher32'])
        self.assertTrue(row['pandas_append'])
        self.assertTrue(row['pandas_format'] == compat.tobytetype('t'))

        for attr_name, table_name in HDF5StorageService.NAME_TABLE_MAPPING.items():
            self.assertTrue(row[table_name])

        self.assertTrue(row['purge_duplicate_comments'])
        self.assertTrue(row['explored_parameters_runs'])
        self.assertTrue(row['results_per_run']==19)
        self.assertTrue(row['derived_parameters_per_run'] == 17)

        hdf5file.close()


    def test_store_items_and_groups(self):

        traj = Trajectory(name='testtraj', filename=make_temp_file('teststoreitems.hdf5'))

        traj.f_store()

        traj.f_add_parameter('group1.test',42, comment= 'TooLong' * pypetconstants.HDF5_STRCOL_MAX_COMMENT_LENGTH)

        traj.f_add_result('testres', 42)

        traj.group1.f_set_annotations(Test=44)

        traj.f_store_items(['test','testres','group1'])


        traj2 = Trajectory(name=traj.v_name, add_time=False,
                           filename=make_temp_file('teststoreitems.hdf5'))

        traj2.f_load(load_results=2,load_parameters=2)

        traj.f_add_result('Im.stored.along.a.path', 43)
        traj.Im.stored.along.v_annotations['wtf'] =4444
        traj.res.f_store_child('Im.stored.along.a.path')


        traj2.res.f_load_child('Im.stored.along.a.path', load_data=2)

        self.compare_trajectories(traj,traj2)


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



    def setUp(self):
        self.set_mode()

        logging.basicConfig(level = logging.INFO)


        self.logfolder = make_temp_file('experiments/tests/Log')

        random.seed()
        self.trajname = make_trajectory_name(self)
        self.filename = make_temp_file('experiments/tests/HDF5/test%s.hdf5' % self.trajname)

        env = Environment(trajectory=self.trajname, filename=self.filename,
                          file_title=self.trajname, log_folder=self.logfolder,
                          log_stdout=False,
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

    def make_run_large_data(self):
        self.env.f_run(add_large_data)

    def make_run(self):

        ### Make a test run
        simple_arg = -13
        simple_kwarg= 13.0
        self.env.f_run(simple_calculations,simple_arg,simple_kwarg=simple_kwarg)

    def test_a_large_run(self):
        self.traj.f_add_parameter('TEST', 'test_run')
        ###Explore
        self.explore_large(self.traj)
        self.make_run_large_data()
        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj,newtraj)


    def test_run(self):
        self.traj.f_add_parameter('TEST', 'test_run')
        ###Explore
        self.explore(self.traj)


        self.make_run()


        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj,newtraj)


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
        newtraj.f_load(name=trajectory_name, load_parameters=2,
                       load_derived_parameters=2,load_results=2,
                       load_other_data=2,
                       index=trajectory_index, as_new=as_new)
        return newtraj


    def test_expand(self):

        ###Explore
        self.traj.f_add_parameter('TEST', 'test_expand')
        self.explore(self.traj)

        self.make_run()

        self.expand()

        print('\n $$$$$$$$$$$$$$$$$ Second Run $$$$$$$$$$$$$$$$$$$$$$$$')
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


        self.env = Environment(trajectory=self.traj,filename=self.filename,
                          file_title=self.trajname, log_folder=self.logfolder,
                          log_stdout=False)

        self.traj = self.env.v_trajectory

        self.traj.f_load(name=traj_name)

        self.expand()

        print('\n $$$$$$$$$$$$ Second Run $$$$$$$$$$ \n')
        self.make_run()

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_update_skeleton()
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

        self.traj.f_delete_item('new.test.group', remove_empty_groups=True)

        with self.assertRaises(pex.DataNotInStorageError):
            self.traj.parameters.f_load_child('new', recursive=True, load_data=pypetconstants.LOAD_SKELETON)



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
            self.traj.purge_duplicate_comments=1
            self.traj.overview.results_runs_summary=0
            self.make_run()

        self.traj.f_get('purge_duplicate_comments').f_unlock()
        self.traj.purge_duplicate_comments=1
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

    def set_mode(self):
        self.mode = 'LOCK'
        self.multiproc = False
        self.ncores = 1
        self.use_pool=True

    def setUp(self):
        self.set_mode()
        logging.basicConfig(level = logging.INFO)

        self.filename = make_temp_file('experiments/tests/HDF5/test.hdf5')
        self.logfolder = make_temp_file('experiments/tests/Log')
        self.trajname = make_trajectory_name(self)

        env = Environment(trajectory=self.trajname,filename=self.filename,
                          file_title=self.trajname, log_folder=self.logfolder,
                          log_stdout=False,
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


        self.env.f_run(multiply)
        traj = self.traj
        self.assertTrue(len(traj) == len(compat.listvalues(self.explore_dict)[0]))

        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj,newtraj)

    def test_f_iter_runs(self):

         ###Explore
        self.explore(self.traj)


        self.env.f_run(multiply)
        traj = self.traj
        self.assertTrue(len(traj) == len(compat.listvalues(self.explore_dict)[0]))

        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        newtraj = self.load_trajectory(trajectory_name=self.traj.v_name,as_new=False)
        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        for idx, run_name in enumerate(self.traj.f_iter_runs()):
            newtraj.v_as_run=run_name
            self.traj.v_as_run == run_name
            self.traj.v_idx = idx
            newtraj.v_idx = idx

            self.assertTrue('run_%08d' % (idx+1) not in traj)

            self.assertTrue(newtraj.z==traj.x*traj.y,' z != x*y: %s != %s * %s' %
                                                  (str(newtraj.z),str(traj.x),str(traj.y)))

        self.assertTrue(traj.v_idx == -1)
        self.assertTrue(traj.v_as_run == 'run_ALL')
        self.assertTrue(newtraj.v_idx == idx)


    def test_expand(self):
        ###Explore
        self.explore(self.traj)

        print(self.env.f_run(multiply))
        traj = self.traj
        self.assertTrue(len(traj) == len(list(compat.listvalues(self.explore_dict)[0])))

        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        traj_name = self.env.v_trajectory.v_name
        del self.env
        self.env = Environment(trajectory=self.traj,filename=self.filename,
                          file_title=self.trajname, log_folder=self.logfolder,
                          log_stdout=False)

        self.traj = self.env.v_trajectory

        self.traj.f_load(name=traj_name)

        self.expand(self.traj)

        self.env.f_run(multiply)
        traj = self.traj
        self.assertTrue(len(traj) == len(compat.listvalues(self.expand_dict)[0])+ len(compat.listvalues(self.explore_dict)[0]))


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

        self.env.f_run(multiply)
        traj = self.traj
        self.assertTrue(len(traj) == len(compat.listvalues(self.explore_dict)[0]))

        self.traj.f_update_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        self.expand(self.traj)

        self.env.f_run(multiply)
        traj = self.traj
        self.assertTrue(len(traj) == len(compat.listvalues(self.expand_dict)[0])+\
                        len(compat.listvalues(self.explore_dict)[0]))

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


def test_runfunc(traj, list_that_changes):
    traj.f_add_result('kkk', list_that_changes[traj.v_idx] + traj.v_idx)
    list_that_changes[traj.v_idx] = 1000

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
    make_run()