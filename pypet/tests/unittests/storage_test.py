__author__ = 'Robert Meyer'

import os

import numpy as np
import pandas as pd
from scipy import sparse as spsp
import tables as pt

from pypet import Trajectory, Parameter, load_trajectory, ArrayParameter, SparseParameter, \
    SparseResult, Result, NNGroupNode, ResultGroup, ConfigGroup, DerivedParameterGroup, \
    ParameterGroup, Environment, pypetconstants, HDF5StorageService
from pypet.tests.testutils.data import TrajectoryComparator
from pypet.tests.testutils.ioutils import make_temp_dir, get_root_logger, \
    parse_args, run_suite, get_log_config, get_log_path
from pypet.utils.comparisons import results_equal
import pypet.pypetexceptions as pex


class FakeResult(Result):
    def _store(self):
        raise RuntimeError('I won`t store')


class FakeResult2(Result):
    def __init__(self, full_name, *args, **kwargs):
        super(FakeResult2, self).__init__(full_name, *args, **kwargs)
        self._store_call = 0
    def _store(self):
        res = {}
        if self._store_call == 0:
            res['hey'] = np.ones((10,10))
        if self._store_call > 0:
            res['fail']=FakeResult # This will faile
        self._store_call += 1
        return res


class MyParamGroup(ParameterGroup):
    pass


class StorageTest(TrajectoryComparator):

    tags = 'unittest', 'trajectory', 'hdf5'

    def test_max_depth_loading_and_storing(self):
        filename = make_temp_dir('newassignment.hdf5')
        traj = Trajectory(filename=filename, overwrite_file=True)

        traj.par.d1 = Parameter('d1.d2.d3.d4.d5', 55)
        traj.f_store(max_depth=4)

        traj = load_trajectory(index=-1, filename=filename)
        traj.f_load(load_data=2)
        self.assertTrue('d3' in traj)
        self.assertFalse('d4' in traj)

        traj = load_trajectory(index=-1, filename=filename, max_depth=3)
        self.assertTrue('d2' in traj)
        self.assertFalse('d3' in traj)

        traj.par.f_remove(recursive=True)
        traj.dpar.d1 = Parameter('d1.d2.d3.d4.d5', 123)

        traj.dpar.f_store_child('d1', recursive=True, max_depth=3)
        traj.dpar.f_remove_child('d1', recursive=True)

        self.assertTrue('d1' not in traj)
        traj.dpar.f_load_child('d1', recursive=True)

        self.assertTrue('d3' in traj)
        self.assertTrue('d4' not in traj)

        traj.dpar.f_remove_child('d1', recursive=True)
        self.assertTrue('d1' not in traj)
        traj.dpar.f_load_child('d1', recursive=True, max_depth=2)

        self.assertTrue('d2' in traj)
        self.assertTrue('d3' not in traj)

        traj.dpar.l1 = Parameter('l1.l2.l3.l4.l5', 123)
        traj.dpar.f_store(recursive=True, max_depth=0)
        self.assertFalse(traj.dpar.l1._stored)

        traj.dpar.f_store(recursive=True, max_depth=4)
        traj.dpar.f_remove()
        self.assertTrue('l1' not in traj)
        traj.dpar.f_load(recursive=True)
        self.assertTrue('l4' in traj)
        self.assertTrue('l5' not in traj)

        traj.dpar.f_remove()
        self.assertTrue('l1' not in traj)
        traj.dpar.f_load(recursive=True, max_depth=3)
        self.assertTrue('l3' in traj)
        self.assertTrue('l4' not in traj)

    def test_file_size_many_params(self):
        filename = make_temp_dir('filesize.hdf5')
        traj = Trajectory(filename=filename, overwrite_file=True, add_time=False)
        npars = 700
        traj.f_store()
        for irun in range(npars):
            par = traj.f_add_parameter('test.test%d' % irun, 42+irun, comment='duh!')
            traj.f_store_item(par)


        size =  os.path.getsize(filename)
        size_in_mb = size/1000000.
        get_root_logger().info('Size is %sMB' % str(size_in_mb))
        self.assertTrue(size_in_mb < 10.0, 'Size is %sMB > 10MB' % str(size_in_mb))

    def test_loading_explored_parameters(self):

        filename = make_temp_dir('load_explored.hdf5')
        traj = Trajectory(filename=filename, overwrite_file=True, add_time=False)
        traj.par.x = Parameter('x', 42, comment='answer')
        traj.f_explore({'x':[1,2,3,4]})
        traj.f_store()
        name = traj.v_name

        traj = Trajectory(filename=filename, add_time=False)
        traj.f_load()
        x = traj.f_get('x')
        self.assertIs(x, traj._explored_parameters['parameters.x'])

    def test_loading_and_storing_empty_containers(self):
        filename = make_temp_dir('empty_containers.hdf5')
        traj = Trajectory(filename=filename, add_time=True)

        # traj.f_add_parameter('empty.dict', {})
        # traj.f_add_parameter('empty.list', [])
        traj.f_add_parameter(ArrayParameter, 'empty.tuple', ())
        traj.f_add_parameter(ArrayParameter, 'empty.array', np.array([], dtype=float))

        spsparse_csc = spsp.csc_matrix((2,10))
        spsparse_csr = spsp.csr_matrix((6660,660))
        spsparse_bsr = spsp.bsr_matrix((3330,2220))
        spsparse_dia = spsp.dia_matrix((1230,1230))

        traj.f_add_parameter(SparseParameter, 'empty.csc', spsparse_csc)
        traj.f_add_parameter(SparseParameter, 'empty.csr', spsparse_csr)
        traj.f_add_parameter(SparseParameter, 'empty.bsr', spsparse_bsr)
        traj.f_add_parameter(SparseParameter, 'empty.dia', spsparse_dia)

        traj.f_add_result(SparseResult, 'empty.all', dict={}, list=[],
                          series = pd.Series(),
                          frame = pd.DataFrame(),
                          **traj.par.f_to_dict(short_names=True, fast_access=True))

        traj.f_store()

        newtraj = load_trajectory(index=-1, filename=filename)

        newtraj.f_load(load_data=2)

        epg = newtraj.par.empty
        self.assertTrue(type(epg.tuple) is tuple)
        self.assertTrue(len(epg.tuple) == 0)

        self.assertTrue(type(epg.array) is np.ndarray)
        self.assertTrue(epg.array.size == 0)

        self.assertTrue(spsp.isspmatrix_csr(epg.csr))
        self.assertTrue(epg.csr.size == 0)

        self.assertTrue(spsp.isspmatrix_csc(epg.csc))
        self.assertTrue(epg.csc.size == 0)

        self.assertTrue(spsp.isspmatrix_bsr(epg.bsr))
        self.assertTrue(epg.bsr.size == 0)

        self.assertTrue(spsp.isspmatrix_dia(epg.dia))
        self.assertTrue(epg.dia.size == 0)

        self.compare_trajectories(traj, newtraj)


    def test_new_assignment_method(self):
        filename = make_temp_dir('newassignment.hdf5')
        traj = Trajectory(filename=filename, add_time=True)

        comment = 'A number'
        traj.par.x = Parameter('', 44, comment)

        self.assertTrue(traj.f_get('x').v_comment == comment)

        traj.x = 45
        self.assertTrue(traj.par.f_get('x').f_get() == 45)

        self.assertTrue(isinstance(traj.f_get('x'), Parameter))

        with self.assertRaises(AttributeError):
            traj.f = Parameter('lll', 444, 'lll')


        traj.f = Parameter('', 444, 'lll')

        self.assertTrue(traj.f_get('f').v_name == 'f')


        conf = traj.conf
        with self.assertRaises(AttributeError):
            conf = traj.conf.jjjj
        traj.f_set_properties(fast_access=True)


        traj.crun = Result('', k=43, m='JJJ')
        self.assertTrue(traj.run_A['k'] == 43)

        with self.assertRaises(AttributeError):
            traj.f_set_properties(j=7)

        with self.assertRaises(AttributeError):
            traj.f_set_properties(depth=7)

        traj.hui = Result('hui', ('444', 'kkkk',), 'l')



        self.assertTrue(traj.f_get('hui')[1] == 'l')


        traj.f_get('hui').f_set(('445', 'kkkk',))

        self.assertTrue(traj.f_get('hui')[1] == 'l')

        self.assertTrue(traj.hui[0] == ('445', 'kkkk',))

        traj.f_add_link('klkikju', traj.par) # for shizzle


        traj.meee = Result('meee.h', 43, hui = 3213, comment='du')

        self.assertTrue(traj.meee.h.h == 43)

        with self.assertRaises(TypeError):
            traj.par.jj = NNGroupNode('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.res.jj = NNGroupNode('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.conf.jj = NNGroupNode('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.dpar.jj = NNGroupNode('jj', comment='mi')

        with self.assertRaises(TypeError):
            traj.par.jj = ResultGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.dpar.jj = ResultGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.conf.jj = ResultGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.jj = ResultGroup('jj', comment='mi')

        with self.assertRaises(TypeError):
            traj.par.jj = ConfigGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.dpar.jj = ConfigGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.res.jj = ConfigGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.jj = ConfigGroup('jj', comment='mi')

        with self.assertRaises(TypeError):
            traj.par.jj = DerivedParameterGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.conf.jj = DerivedParameterGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.res.jj = DerivedParameterGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.jj = DerivedParameterGroup('jj', comment='mi')

        with self.assertRaises(TypeError):
            traj.dpar.jj = ParameterGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.res.jj = ParameterGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.conf.jj = ParameterGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.jj = ParameterGroup('jj', comment='mi')

        traj.par.jj = ParameterGroup('jj', comment='mi')
        traj.res.jj = ResultGroup('jj', comment='mi')
        traj.jj = NNGroupNode('jj')
        cg = ConfigGroup('a.g')
        traj.conf.a = cg

        self.assertTrue(traj.f_get('conf.a.g', shortcuts=False) is cg)

        dg = DerivedParameterGroup('ttt')
        traj.dpar.ttt = dg

        self.assertTrue(traj.f_get('dpar.ttt', shortcuts=False) is dg)

        traj.mylink = traj.par

        self.assertTrue(traj.mylink is traj.par)

        traj.vvv = NNGroupNode('', comment='kkk')

        self.assertTrue(traj.vvv.v_full_name == 'vvv')

        self.assertTrue(traj.par.jj.v_name == 'jj')

        traj.ff = MyParamGroup('ff')

        traj.par.g = MyParamGroup('')

        pg = traj.f_add_parameter_group(comment='gg', full_name='me')
        self.assertTrue(traj.par.me is pg)

        traj.f_store()

        traj = load_trajectory(index=-1, filename=filename, dynamic_imports=MyParamGroup)

        self.assertTrue(isinstance(traj.ff, MyParamGroup))
        self.assertTrue(isinstance(traj.par.g, MyParamGroup))

        traj.par.hiho = Parameter('hiho', 42, comment='you')
        traj.par.g1 = Parameter('g1.g2.g3.g4.g5', 43)

        self.assertTrue(traj.hiho == 42)
        self.assertTrue(isinstance(traj.par.g1, ParameterGroup ))
        self.assertTrue(isinstance(traj.par.g3, ParameterGroup ))
        self.assertTrue(traj.g3.g5 == 43)


    def test_shortenings_of_names(self):
        traj = Trajectory(filename=make_temp_dir('testshortening.hdf5'), add_time=True)
        traj.f_aconf('g', 444)
        self.assertTrue(isinstance(traj.f_get('g'), Parameter))
        self.assertTrue(traj.conf.g == 444)

        traj.f_apar('g', 444)
        self.assertTrue(isinstance(traj.par.f_get('g'), Parameter))
        self.assertTrue(traj.par.g == 444)

        traj.f_adpar('g', 445)
        self.assertTrue(isinstance(traj.derived_parameters.f_get('g'), Parameter))
        self.assertTrue(traj.dpar.g == 445)

        traj.f_ares('g', 454)
        self.assertTrue(isinstance(traj.res.f_get('g'), Result))
        self.assertTrue(traj.res.g == 454)


    def test_storage_service_errors(self):

        traj = Trajectory(filename=make_temp_dir('testnoservice.hdf5'), add_time=True)

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
            traj.f_load(name='test', index=1)

        with self.assertRaises(RuntimeError):
            traj.v_storage_service.store('LIST', [('LEAF',None,None,None,None)],
                                         trajectory_name = traj.v_name)

        with self.assertRaises(ValueError):
            traj.f_load(index=9999)

        with self.assertRaises(ValueError):
            traj.f_load(name='Non-Existising-Traj')

    def test_storing_and_loading_groups(self):
        filename = make_temp_dir('grpgrp.hdf5')
        traj = Trajectory(name='traj', add_time=True, filename=filename)
        res=traj.f_add_result('aaa.bbb.ccc.iii', 42, 43, comment=7777 * '6')
        traj.ccc.v_annotations['gg']=4
        res=traj.f_add_result('aaa.ddd.eee.jjj', 42, 43, comment=777 * '6')
        traj.ccc.v_annotations['j'] = 'osajdsojds'
        traj.f_store(only_init=True)
        traj.f_store_item('aaa', recursive=True)
        newtraj = load_trajectory(traj.v_name, filename=filename, load_all=2)

        self.compare_trajectories(traj, newtraj)

        traj.iii.f_set(55)

        self.assertFalse(results_equal(traj.iii, newtraj.iii))

        traj.aaa.f_store(recursive=True, store_data=3)

        newtraj.bbb.f_load(recursive=True, load_data=3)

        self.compare_trajectories(traj, newtraj)

        traj.ccc.v_annotations['gg'] = 5
        traj.f_load(load_data=3)
        self.assertTrue(traj.ccc.v_annotations['gg'] == 4)
        traj.ccc.v_annotations['gg'] = 5
        traj.f_store(store_data=3)
        newtraj.f_load(load_data=2)
        self.assertTrue(newtraj.ccc.v_annotations['gg'] == 4)
        newtraj.f_load(load_data=3)
        self.assertTrue(newtraj.ccc.v_annotations['gg'] == 5)

        traj.ccc.f_add_link('link', res)
        traj.f_store_item(traj.ccc, store_data=3, with_links=False)

        newtraj.f_load(load_data=3)
        self.assertTrue('link' not in newtraj.ccc)

        traj.f_store_item(traj.ccc, store_data=3, with_links=True, recursive=True)

        newtraj.f_load_item(newtraj.ccc, with_links=False, recursive=True)
        self.assertTrue('link' not in newtraj.ccc)

        newtraj.f_load_item(newtraj.ccc, recursive=True)
        self.assertTrue('link' in newtraj.ccc)


    def test_store_overly_long_comment(self):
        filename = make_temp_dir('remove_errored.hdf5')
        traj = Trajectory(name='traj', add_time=True, filename=filename)
        res=traj.f_add_result('iii', 42, 43, comment=7777 * '6')
        traj.f_store()
        traj.f_remove_child('results', recursive=True)
        traj.f_load_child('results', recursive=True)
        self.assertTrue(traj.iii.v_comment == 7777 * '6')

    def test_removal_of_error_parameter(self):

        filename = make_temp_dir('remove_errored.hdf5')
        traj = Trajectory(name='traj', add_time=True, filename=filename)
        traj.f_add_result('iii', 42)
        traj.f_add_result(FakeResult, 'j.j.josie', 43)

        file = traj.v_storage_service.filename
        traj.f_store(only_init=True)
        with self.assertRaises(RuntimeError):
            traj.f_store()

        with pt.open_file(file, mode='r') as fh:
            jj = fh.get_node(where='/%s/results/j/j' % traj.v_name)
            self.assertTrue('josie' not in jj)

        traj.j.j.f_remove_child('josie')
        traj.j.j.f_add_result(FakeResult2, 'josie2', 444)

        traj.f_store()
        with self.assertRaises(pex.NoSuchServiceError):
            traj.f_store_child('results', recursive=True)

        with pt.open_file(file, mode='r') as fh:
            jj = fh.get_node(where='/%s/results/j/j' % traj.v_name)
            self.assertTrue('josie2' in jj)
            josie2 =jj._f_get_child('josie2')
            self.assertTrue('hey' in josie2)
            self.assertTrue('fail' not in josie2)


    def test_maximum_overview_size(self):

        filename = make_temp_dir('maxisze.hdf5')

        env = Environment(trajectory='Testmigrate', filename=filename,

                          log_config=get_log_config(), add_time=True)

        traj = env.v_trajectory
        for irun in range(pypetconstants.HDF5_MAX_OVERVIEW_TABLE_LENGTH):
            traj.f_add_parameter('f%d.x' % irun, 5)

        traj.f_store()


        store = pt.open_file(filename, mode='r+')
        table = store.root._f_get_child(traj.v_name).overview.parameters_overview
        self.assertEquals(table.nrows, pypetconstants.HDF5_MAX_OVERVIEW_TABLE_LENGTH)
        store.close()

        for irun in range(pypetconstants.HDF5_MAX_OVERVIEW_TABLE_LENGTH,
                  2*pypetconstants.HDF5_MAX_OVERVIEW_TABLE_LENGTH):
            traj.f_add_parameter('f%d.x' % irun, 5)

        traj.f_store()

        store = pt.open_file(filename, mode='r+')
        table = store.root._f_get_child(traj.v_name).overview.parameters_overview
        self.assertEquals(table.nrows, pypetconstants.HDF5_MAX_OVERVIEW_TABLE_LENGTH)
        store.close()

        env.f_disable_logging()

    def test_overwrite_annotations_and_results(self):

        filename = make_temp_dir('overwrite.hdf5')

        env = Environment(trajectory='testoverwrite', filename=filename,
                          log_config=get_log_config(), overwrite_file=True)

        traj = env.v_traj

        traj.f_add_parameter('grp.x', 5, comment='hi')
        traj.grp.v_comment='hi'
        traj.grp.v_annotations['a'] = 'b'

        traj.f_store()

        traj.f_remove_child('parameters', recursive=True)

        traj.f_load(load_data=2)

        self.assertTrue(traj.x == 5)
        self.assertTrue(traj.grp.v_comment == 'hi')
        self.assertTrue(traj.grp.v_annotations['a'] == 'b')

        traj.f_get('x').f_unlock()
        traj.grp.x = 22
        traj.f_get('x').v_comment='hu'
        traj.grp.v_annotations['a'] = 'c'
        traj.grp.v_comment = 'hu'

        traj.f_store_item(traj.f_get('x'), store_data=3)
        traj.f_store_item(traj.grp, store_data=3)

        traj.f_remove_child('parameters', recursive=True)

        traj.f_load(load_data=2)

        self.assertTrue(traj.x == 22)
        self.assertTrue(traj.grp.v_comment == 'hu')
        self.assertTrue(traj.grp.v_annotations['a'] == 'c')

        env.f_disable_logging()


    def test_migrations(self):

        traj = Trajectory(name='Testmigrate', filename=make_temp_dir('migrate.hdf5'),
                          add_time=True)

        traj.f_add_result('I.am.a.mean.resu', 42, comment='Test')
        traj.f_add_derived_parameter('ffa', 42)

        traj.f_store()

        new_file = make_temp_dir('migrate2.hdf5')
        traj.f_migrate(filename=new_file)

        traj.f_store()

        new_traj = Trajectory()

        new_traj.f_migrate(new_name=traj.v_name, filename=new_file, in_store=True)

        new_traj.v_auto_load=True

        self.assertTrue(new_traj.results.I.am.a.mean.resu == 42)

    def test_wildcard_search(self):

        traj = Trajectory(name='Testwildcard', filename=make_temp_dir('wilcard.hdf5'),
                          add_time=True)

        traj.f_add_parameter('expl', 2)
        traj.f_explore({'expl':[1,2,3,4]})

        traj.f_add_result('wc2test.$.hhh', 333)
        traj.f_add_leaf('results.wctest.run_00000000.jjj', 42)
        traj.f_add_result('results.wctest.run_00000001.jjj', 43)
        traj.f_add_result('results.wctest.%s.jjj' % traj.f_wildcard('$', -1), 43)

        traj.v_crun = 1

        self.assertTrue(traj.results.wctest['$'].jjj==43)
        self.assertTrue(traj.results.wc2test.crun.hhh==333)

        traj.f_store()

        get_root_logger().info('Removing child1')

        traj.f_remove_child('results', recursive=True)

        get_root_logger().info('Doing auto-load')
        traj.v_auto_load = True

        self.assertTrue(traj.results.wctest['$'].jjj==43)
        self.assertTrue(traj.results.wc2test.crun.hhh==333)

        get_root_logger().info('Removing child2')

        traj.f_remove_child('results', recursive=True)

        get_root_logger().info('auto-loading')
        traj.v_auto_load = True

        self.assertTrue(traj.results.wctest[-1].jjj==43)
        self.assertTrue(traj.results.wc2test[-1].hhh==333)

        get_root_logger().info('Removing child3')
        traj.f_remove_child('results', recursive=True)

        get_root_logger().info('auto-loading')
        traj.v_auto_load = True

        self.assertTrue(traj.results.wctest[1].jjj==43)
        self.assertTrue(traj.results.wc2test[-1].hhh==333)

        get_root_logger().info('Done with wildcard test')

    def test_store_and_load_large_dictionary(self):
        traj = Trajectory(name='Testlargedict', filename=make_temp_dir('large_dict.hdf5'),
                          add_time=True)

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

        traj2 = Trajectory(filename=make_temp_dir('large_dict.hdf5'),
                           add_time=True)

        traj2.f_load(name=traj_name, load_data=2)

        self.compare_trajectories(traj, traj2)


    def test_auto_load(self):


        traj = Trajectory(name='Testautoload', filename=make_temp_dir('autoload.hdf5'),
                          add_time=True)

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

        with self.assertRaises(pex.DataNotInStorageError):
            traj.kdsfdsf

    def test_get_default(self):


        traj = Trajectory(name='Testgetdefault', filename=make_temp_dir('autoload.hdf5'),
                          add_time=True)

        traj.v_auto_load = True

        traj.f_add_result('I.am.$.a.mean.resu', 42, comment='Test')

        val = traj.f_get_default('jjjjjjjjjj', 555)
        self.assertTrue(val==555)

        traj.f_store()

        traj.f_remove_child('results', recursive=True)




        val = traj.f_get_default('res.I.am.crun.a.mean.answ', 444, auto_load=True)

        self.assertTrue(val==444)

        val = traj.f_get_default('res.I.am.crun.a.mean.resu', auto_load=True, fast_access=True)

        self.assertTrue(val==42)

        with self.assertRaises(Exception):
            traj.kdsfdsf


    def test_version_mismatch(self):
        traj = Trajectory(name='TestVERSION', filename=make_temp_dir('testversionmismatch.hdf5'),
                          add_time=True)

        traj.f_add_parameter('group1.test',42)

        traj.f_add_result('testres', 42)

        traj.group1.f_set_annotations(Test=44)

        traj._version='0.1a.1'

        traj.f_store()

        traj2 = Trajectory(name=traj.v_name, add_time=False,
                           filename=make_temp_dir('testversionmismatch.hdf5'))

        with self.assertRaises(pex.VersionMismatchError):
            traj2.f_load(load_parameters=2, load_results=2)

        traj2.f_load(load_parameters=2, load_results=2, force=True)

        self.compare_trajectories(traj,traj2)

        get_root_logger().info('Mismatch testing done!')

    def test_fail_on_wrong_kwarg(self):
        with self.assertRaises(ValueError):
            filename = 'testsfail.hdf5'
            env = Environment(filename=make_temp_dir(filename),
                          log_stdout=True,
                          log_config=get_log_config(),
                          logger_names=('STDERROR', 'STDOUT'),
                          foo='bar')

    def test_no_run_information_loading(self):
        filename = make_temp_dir('testnoruninfo.hdf5')
        traj = Trajectory(name='TestDelete',
                          filename=filename,
                          add_time=True)

        length = 100000
        traj.par.x = Parameter('', 42)
        traj.f_explore({'x': range(length)})

        traj.f_store()

        traj = load_trajectory(index=-1, filename=filename, with_run_information=False)
        self.assertEqual(len(traj), length)
        self.assertEqual(len(traj._run_information), 1)

    def test_delete_whole_subtrees(self):
        filename = make_temp_dir('testdeltree.hdf5')
        traj = Trajectory(name='TestDelete',
                          filename=filename, large_overview_tables=True,
                          add_time=True)

        res = traj.f_add_result('mytest.yourtest.test', a='b', c='d')
        dpar = traj.f_add_derived_parameter('mmm.gr.dpdp', 666)


        res = traj.f_add_result('hhh.ll', a='b', c='d')
        res = traj.f_add_derived_parameter('hhh.gg', 555)

        traj.f_store()

        with pt.open_file(filename) as fh:
            daroot = fh.root._f_get_child(traj.v_name)
            dpar_table = daroot.overview.derived_parameters_overview
            self.assertTrue(len(dpar_table) == 2)
            res_table = daroot.overview.results_overview
            self.assertTrue((len(res_table)) == 2)

        with self.assertRaises(TypeError):
            traj.f_remove_item(traj.yourtest)

        with self.assertRaises(TypeError):
            traj.f_delete_item(traj.yourtest)

        traj.f_remove_item(traj.yourtest, recursive=True)

        self.assertTrue('mytest' in traj)
        self.assertTrue('yourtest' not in traj)

        traj.f_load(load_data=2)

        self.assertTrue('yourtest.test' in traj)

        traj.f_delete_item(traj.yourtest, recursive=True, remove_from_trajectory=True)
        traj.f_delete_item(traj.mmm, recursive=True, remove_from_trajectory=True)

        traj.f_load(load_data=2)

        self.assertTrue('yourtest.test' not in traj)
        self.assertTrue('yourtest' not in traj)

        with pt.open_file(filename) as fh:
            daroot = fh.root._f_get_child(traj.v_name)
            dpar_table = daroot.overview.derived_parameters_overview
            self.assertTrue(len(dpar_table) == 2)
            res_table = daroot.overview.results_overview
            self.assertTrue((len(res_table)) == 2)

        traj.f_add_parameter('ggg', 43)
        traj.f_add_parameter('hhh.mmm', 45)
        traj.f_add_parameter('jjj', 55)
        traj.f_add_parameter('hhh.nnn', 55555)

        traj.f_explore({'ggg':[1,2,3]})

        traj.f_store()

        with pt.open_file(filename) as fh:
            daroot = fh.root._f_get_child(traj.v_name)
            par_table = daroot.overview.parameters_overview
            self.assertTrue(len(par_table) == 4)

        traj.f_delete_item('par.hhh', recursive=True, remove_from_trajectory=True)

        traj.f_add_parameter('saddsdfdsfd', 111)
        traj.f_store()

        with pt.open_file(filename) as fh:
            daroot = fh.root._f_get_child(traj.v_name)
            par_table = daroot.overview.parameters_overview
            self.assertTrue(len(par_table) == 5)

        # with self.assertRaises(TypeError):
        #     # We cannot delete something containing an explored parameter
        #     traj.f_delete_item('par', recursive=True)

        # with self.assertRaises(TypeError):
        #     traj.f_delete_item('ggg')

    def test_delete_links(self):
        traj = Trajectory(name='TestDelete',
                          filename=make_temp_dir('testpartiallydel.hdf5'),
                          add_time=True)

        res = traj.f_add_result('mytest.test', a='b', c='d')

        traj.f_add_link('x.y', res)
        traj.f_add_link('x.g.h', res)

        traj.f_store()

        traj.f_remove_child('x', recursive=True)
        traj.f_load()

        self.assertEqual(traj.x.y.a, traj.test.a)
        self.assertEqual(traj.x.g.h.a, traj.test.a)

        traj.f_delete_link('x.y', remove_from_trajectory=True)
        traj.f_delete_link((traj.x.g, 'h'), remove_from_trajectory=True)

        traj.f_load()

        with self.assertRaises(AttributeError):
            traj.x.g.h


    def test_partially_delete_stuff(self):
        traj = Trajectory(name='TestDelete',
                          filename=make_temp_dir('testpartiallydel.hdf5'),
                          add_time=True)

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

        traj.f_delete_item(res, remove_from_trajectory=True)

        self.assertTrue('results' in traj)
        self.assertTrue(res not in traj)

    # def test_throw_warning_if_old_kw_is_used(self):
    #
    #     filename = make_temp_dir('hdfwarning.hdf5')
    #
    #     with warnings.catch_warnings(record=True) as w:
    #         warnings.simplefilter("always", DeprecationWarning, append=False)
    #         env = Environment(trajectory='test', filename=filename,
    #                           dynamically_imported_classes=[],
    #                           log_config=get_log_config(), add_time=True)
    #         self.assertEqual(len(w), 1)
    #
    #     with warnings.catch_warnings(record=True) as w:
    #         warnings.simplefilter("always", DeprecationWarning, append=False)
    #         traj = Trajectory(dynamically_imported_classes=[])
    #         self.assertEqual(len(w), 1)
    #
    #     traj = env.v_trajectory
    #     traj.f_store()
    #
    #     with warnings.catch_warnings(record=True) as w:
    #         warnings.simplefilter("always", DeprecationWarning, append=False)
    #         traj.f_load(dynamically_imported_classes=[])
    #         self.assertEqual(len(w), 1)
    #
    #     env.f_disable_logging()

    def test_overwrite_stuff(self):
        traj = Trajectory(name='TestOverwrite', filename=make_temp_dir('testowrite.hdf5'),
                          add_time=True)

        res = traj.f_add_result('mytest.test', a='b', c='d')

        traj.f_store()

        res['a'] = np.array([1,2,3])
        res['c'] = 123445

        traj.f_store_item(res, overwrite='a', complevel=4)

        # Should emit a warning
        traj.f_store_item(res, overwrite=['a', 'b'])

        traj.f_load(load_results=3)

        res = traj.test

        self.assertTrue((res['a']==np.array([1,2,3])).all())
        self.assertTrue(res['c']=='d')

        res['c'] = 123445

        traj.f_store_item(res, store_data=3)
        res.f_empty()

        traj.f_load(load_results=3)

        self.assertTrue(traj.test['c']==123445)

    def test_loading_as_new(self):
        filename = make_temp_dir('asnew.h5')
        traj = Trajectory(name='TestPartial', filename=filename, add_time=True)

        traj.f_add_parameter('x', 3)
        traj.f_add_parameter('y', 2)

        traj.f_explore({'x': [12,3,44], 'y':[1,23,4]})

        traj.f_store()

        traj = load_trajectory(name=traj.v_name, filename=filename)

        with self.assertRaises(TypeError):
            traj.f_shrink()

        traj = load_trajectory(name=traj.v_name, filename=filename, as_new=True,
                               new_name='TestTraj', add_time=False)

        self.assertTrue(traj.v_name == 'TestTraj')

        self.assertEqual(len(traj), 3)

        self.assertEqual(len(traj._explored_parameters), 2)

        traj.f_shrink()

        self.assertTrue(len(traj) == 1)


    def test_partial_loading(self):
        traj = Trajectory(name='TestPartial', filename=make_temp_dir('testpartially.hdf5'),
                          add_time=True)

        res = traj.f_add_result('mytest.test', a='b', c='d')

        traj.f_store()

        traj.f_remove_child('results', recursive=True)

        traj.f_load_skeleton()

        traj.f_load_item(traj.test, load_only=['a', 'x'])

        self.assertTrue('a' in traj.test)
        self.assertTrue('c' not in traj.test)

        traj.f_remove_child('results', recursive=True)

        traj.f_load_skeleton()

        load_except= ['c', 'd']
        traj.f_load_item(traj.test, load_except=load_except)

        self.assertTrue(len(load_except)==2)

        self.assertTrue('a' in traj.test)
        self.assertTrue('c' not in traj.test)

        with self.assertRaises(ValueError):
            traj.f_load_item(traj.test, load_except=['x'], load_only=['y'])


    def test_hdf5_settings_and_context(self):

        filename = make_temp_dir('hdfsettings.hdf5')
        with Environment('testraj', filename=filename,
                         add_time=True,
                         comment='',
                         dynamic_imports=None,
                         log_config=None,
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
                         derived_parameters_per_run=17) as env:

            traj = env.v_trajectory

            traj.f_store()

            hdf5file = pt.open_file(filename=filename)

            table= hdf5file.root._f_get_child(traj.v_name)._f_get_child('overview')._f_get_child('hdf5_settings')

            row = table[0]

            self.assertTrue(row['complevel'] == 4)

            self.assertTrue(row['complib'] == 'zlib'.encode('utf-8'))

            self.assertTrue(row['shuffle'])
            self.assertTrue(row['fletcher32'])
            self.assertTrue(row['pandas_format'] == 't'.encode('utf-8'))

            for attr_name, table_name in HDF5StorageService.NAME_TABLE_MAPPING.items():
                self.assertTrue(row[table_name])

            self.assertTrue(row['purge_duplicate_comments'])
            self.assertTrue(row['results_per_run']==19)
            self.assertTrue(row['derived_parameters_per_run'] == 17)

            hdf5file.close()


    def test_store_items_and_groups(self):

        traj = Trajectory(name='testtraj', filename=make_temp_dir('teststoreitems.hdf5'),
                          add_time=True)

        traj.f_store()

        traj.f_add_parameter('group1.test',42, comment= 'TooLong' * pypetconstants.HDF5_STRCOL_MAX_COMMENT_LENGTH)

        traj.f_add_result('testres', 42)

        traj.group1.f_set_annotations(Test=44)

        traj.f_store_items(['test','testres','group1'])


        traj2 = Trajectory(name=traj.v_name, add_time=False,
                           filename=make_temp_dir('teststoreitems.hdf5'))

        traj2.f_load(load_parameters=2, load_results=2)

        traj.f_add_result('Im.stored.along.a.path', 43)
        traj.Im.stored.along.v_annotations['wtf'] =4444
        traj.res.f_store_child('Im.stored.along.a.path')


        traj2.res.f_load_child('Im.stored.along.a.path', load_data=2)

        self.compare_trajectories(traj,traj2)


if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)