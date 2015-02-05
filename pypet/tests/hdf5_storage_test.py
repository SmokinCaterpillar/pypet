

__author__ = 'Robert Meyer'

import numpy as np
import pandas as pd
import os
import warnings
import platform
from pypet.parameter import Parameter, PickleParameter, ArrayParameter, PickleResult
from pypet.trajectory import Trajectory, load_trajectory
from pypet.utils.explore import cartesian_product
from pypet.environment import Environment
from pypet.storageservice import HDF5StorageService
from pypet import pypetconstants, BaseParameter, BaseResult
from pypet.utils.comparisons import results_equal
import logging
logging.basicConfig(level=logging.INFO)
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
import pypet.utils.ptcompat as ptcompat
from pypet import Result, NNGroupNode,Parameter, ParameterGroup, ResultGroup, \
    DerivedParameterGroup, ConfigGroup
import time

import tables as pt

from pypet.tests.test_helpers import add_params, create_param_dict, simple_calculations, make_run,\
    make_temp_file, TrajectoryComparator, multiply, make_trajectory_name

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

class SlowResult(Result):
    def _load(self, load_dict):
        time.sleep(3)
        super(SlowResult, self)._load(load_dict)

class MyParamGroup(ParameterGroup):
    pass

def add_one_particular_item(traj, store_full):
    traj.hi = 42, 'hi!'
    traj.f_store(store_full_in_run=store_full)
    traj.f_remove_child('hi')

class FullStorageTest(TrajectoryComparator):

    def test_not_full_store(self):
        filename = make_temp_file('full_store.hdf5')
        logfolder = make_temp_file('logs')
        with Environment(log_folder=logfolder, filename=filename) as env:

            traj = env.v_trajectory

            traj.par.x = 3, 'jj'

            traj.f_explore({'x': [1,2,3]})

            env.f_run(add_one_particular_item, False)

            traj = load_trajectory(index=-1, filename=filename)

            self.assertTrue('hi' not in traj)

    def test_full_store(self):
        filename = make_temp_file('full_store.hdf5')
        logfolder = make_temp_file('logs')
        with Environment(log_folder=logfolder, filename=filename) as env:

            traj = env.v_trajectory

            traj.par.x = 3, 'jj'

            traj.f_explore({'x': [1,2,3]})

            env.f_run(add_one_particular_item, True)

            traj = load_trajectory(index=-1, filename=filename)

            self.assertTrue('hi' in traj)

class StorageTest(TrajectoryComparator):

    def test_new_assignment_method(self):
        filename = make_temp_file('newassignment.hdf5')
        traj = Trajectory(filename=filename)

        comment = 'A number'
        traj.par.x = 44, comment

        self.assertTrue(traj.f_get('x').v_comment == comment)


        traj.x = 45
        self.assertTrue(traj.par.f_get('x').f_get() == 45)

        self.assertTrue(isinstance(traj.f_get('x'), Parameter))

        traj.f = Parameter('lll', 444, 'lll')

        self.assertTrue(traj.f_get('f').v_name == 'f')

        traj.res.k = 22, 'Hi'
        self.assertTrue(isinstance(traj.f_get('k'), Result))
        self.assertTrue(traj.f_get('k').v_comment == 'Hi')

        with self.assertRaises(AttributeError):
            traj.res.k = 33, 'adsd'

        conf = traj.conf
        with self.assertRaises(AttributeError):
            conf = traj.conf.jjjj
        traj.f_set_properties(fast_access=True)


        traj.crun = 43, 'JJJ'
        self.assertTrue(traj.run_A == 43)

        with self.assertRaises(AttributeError):
            traj.f_set_properties(j=7)

        with self.assertRaises(AttributeError):
            traj.f_set_properties(depth=7)

        traj.hui = (('444', 'kkkk',), 'l')



        self.assertTrue(traj.f_get('hui').v_comment == 'l')

        with self.assertRaises(AttributeError):
            traj.hui = ('445', 'kkkk',)

        traj.f_get('hui').f_set(('445', 'kkkk',))

        self.assertTrue(traj.f_get('hui').v_comment == 'l')

        self.assertTrue(traj.hui == ('445', 'kkkk',))

        traj.f_add_link('klkikju', traj.par) # for shizzle


        traj.meee = Result('h', 43, hui = 3213, comment='du')

        self.assertTrue(traj.meee.h.h == 43)

        with self.assertRaises(TypeError):
            traj.par.mu = NNGroupNode('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.res.mu = NNGroupNode('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.conf.mu = NNGroupNode('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.dpar.mu = NNGroupNode('jj', comment='mi')

        with self.assertRaises(TypeError):
            traj.par.mu = ResultGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.dpar.mu = ResultGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.conf.mu = ResultGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.mu = ResultGroup('jj', comment='mi')

        with self.assertRaises(TypeError):
            traj.par.mu = ConfigGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.dpar.mu = ConfigGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.res.mu = ConfigGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.mu = ConfigGroup('jj', comment='mi')

        with self.assertRaises(TypeError):
            traj.par.mu = DerivedParameterGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.conf.mu = DerivedParameterGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.res.mu = DerivedParameterGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.mu = DerivedParameterGroup('jj', comment='mi')

        with self.assertRaises(TypeError):
            traj.dpar.mu = ParameterGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.res.mu = ParameterGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.conf.mu = ParameterGroup('jj', comment='mi')
        with self.assertRaises(TypeError):
            traj.mu = ParameterGroup('jj', comment='mi')

        traj.par.mu = ParameterGroup('jj', comment='mi')
        traj.res.mus = ResultGroup('jj', comment='mi')
        traj.mu = NNGroupNode('jj')
        cg = ConfigGroup('a.g')
        traj.conf.a = cg

        self.assertTrue(traj.f_get('conf.a.a.g', shortcuts=False) is cg)

        dg = DerivedParameterGroup('ttt')
        traj.dpar.ttt = dg

        self.assertTrue(traj.f_get('dpar.ttt', shortcuts=False) is dg)

        traj.mylink = traj.par

        self.assertTrue(traj.mylink is traj.par)

        traj.vvv = NNGroupNode('', comment='kkk')

        self.assertTrue(traj.vvv.v_full_name == 'vvv')

        self.assertTrue(traj.par.mu.v_name == 'mu')

        traj.rrr = MyParamGroup('ff')

        traj.par.g = MyParamGroup('')

        pg = traj.f_add_parameter_group(comment='gg', full_name='me')
        self.assertTrue(traj.par.me is pg)

        traj.f_store()

        traj = load_trajectory(index=-1, filename=filename, dynamic_imports=MyParamGroup)

        self.assertTrue(isinstance(traj.rrr, NNGroupNode))
        self.assertTrue(isinstance(traj.rrr.ff, MyParamGroup))
        self.assertTrue(isinstance(traj.par.g, MyParamGroup))

        traj.par = Parameter('hiho', 42, comment='you')
        traj.par = Parameter('g1.g2.g3.g4.g5', 43)

        self.assertTrue(traj.hiho == 42)
        self.assertTrue(isinstance(traj.par.g1, ParameterGroup ))
        self.assertTrue(isinstance(traj.par.g3, ParameterGroup ))
        self.assertTrue(traj.g3.g5 == 43)


    def test_shortenings_of_names(self):
        traj = Trajectory(filename=make_temp_file('testshortening.hdf5'))
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
            traj.f_load(name='test', index=1)

        with self.assertRaises(RuntimeError):
            traj.v_storage_service.store('LIST', [('LEAF',None,None,None,None)], trajectory_name = traj.v_name)

        with self.assertRaises(ValueError):
            traj.f_load(index=9999)

        with self.assertRaises(ValueError):
            traj.f_load(name='Non-Existising-Traj')

    def test_storing_and_loading_groups(self):
        filename = make_temp_file('grpgrp.hdf5')
        traj = Trajectory(name='traj', add_time=True, filename=filename)
        res=traj.f_add_result('aaa.bbb.ccc.iii', 42, 43, comment=7777 * '6')
        traj.ccc.v_annotations['gg']=4
        res=traj.f_add_result('aaa.ddd.eee.jjj', 42, 43, comment=7777 * '6')
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
        filename = make_temp_file('remove_errored.hdf5')
        traj = Trajectory(name='traj', add_time=True, filename=filename)
        res=traj.f_add_result('iii', 42, 43, comment=7777 * '6')
        traj.f_store()
        traj.f_remove_child('results', recursive=True)
        traj.f_load_child('results', recursive=True)
        self.assertTrue(traj.iii.v_comment == 7777 * '6')

    def test_removal_of_error_parameter(self):

        filename = make_temp_file('remove_errored.hdf5')
        traj = Trajectory(name='traj', add_time=True, filename=filename)
        traj.f_add_result('iii', 42)
        traj.f_add_result(FakeResult, 'j.j.josie', 43)

        file = traj.v_storage_service.filename
        traj.f_store(only_init=True)
        with self.assertRaises(RuntimeError):
            traj.f_store()

        with ptcompat.open_file(file, mode='r') as fh:
            jj = ptcompat.get_node(fh, where='/%s/results/j/j' % traj.v_name)
            self.assertTrue('josie' not in jj)

        traj.j.j.f_remove_child('josie')
        traj.j.j.f_add_result(FakeResult2, 'josie2', 444)

        traj.f_store()
        with self.assertRaises(pex.NoSuchServiceError):
            traj.f_store_child('results', recursive=True)

        with ptcompat.open_file(file, mode='r') as fh:
            jj = ptcompat.get_node(fh, where='/%s/results/j/j' % traj.v_name)
            self.assertTrue('josie2' in jj)
            josie2 = ptcompat.get_child(jj, 'josie2')
            self.assertTrue('hey' in josie2)
            self.assertTrue('fail' not in josie2)


    def test_clean_up_multiple_table_entries(self):

        filename = make_temp_file('cleanup.hdf5')

        env = Environment(trajectory='Testmigrate', filename=filename,
                          log_folder=make_temp_file('logs'))
        logpath = env.v_log_path
        traj = env.v_trajectory
        traj.f_add_parameter('x', 5)

        traj.f_store()

        traj.f_delete_item(traj.f_get('x'))

        traj.f_get('x').f_unlock()
        traj.par.x = 10

        traj.f_add_parameter('y', 43)

        store = ptcompat.open_file(filename, mode='r+')
        table = ptcompat.get_child(store.root,traj.v_name).overview.parameters
        self.assertTrue(table.nrows == 1)

        store.close()

        traj.f_store_item(traj.f_get('y'))
        traj.f_store_item(traj.f_get('x'))

        store = ptcompat.open_file(filename, mode='r+')
        table = ptcompat.get_child(store.root,traj.v_name).overview.parameters
        self.assertTrue(table.nrows == 3)

        store.close()

        traj.f_delete_item(traj.f_get('x'))


        store = ptcompat.open_file(filename, mode='r+')
        table = ptcompat.get_child(store.root,traj.v_name).overview.parameters
        self.assertTrue(table.nrows == 1)

        store.close()

        with open(os.path.join(logpath, 'main.txt')) as fh:
            text = fh.read()

            etext ='appears more than once in table'
            self.assertTrue(etext in text)

        env.f_disable_logging()

    def test_clean_up_multiple_table_entries2(self):

        filename = make_temp_file('cleanup.hdf5')

        env = Environment(trajectory='Testmigrate2', filename=filename,
                          log_folder=make_temp_file('logs'))
        logpath = env.v_log_path
        traj = env.v_trajectory
        traj.f_add_parameter('x', 5)

        traj.f_store()

        traj.f_delete_item(traj.f_get('x'))

        traj.f_add_parameter('y', 43)

        store = ptcompat.open_file(filename, mode='r+')
        table = ptcompat.get_child(store.root,traj.v_name).overview.parameters
        self.assertTrue(table.nrows == 1)

        store.close()

        traj.f_store_item(traj.f_get('y'))
        traj.f_store_item(traj.f_get('x'))

        traj.f_get('x').f_unlock()
        traj.par.x = 10

        traj.f_store_item(traj.f_get('x'), overwrite=True)

        store = ptcompat.open_file(filename, mode='r+')
        table = ptcompat.get_child(store.root,traj.v_name).overview.parameters
        self.assertTrue(table.nrows == 2)
        self.assertTrue(compat.tostr(table[0]['value']) == '10')

        store.close()


        with open(os.path.join(logpath, 'main.txt')) as fh:
            text = fh.read()

            etext ='appears more than once in table'
            self.assertTrue(etext in text)

        env.f_disable_logging()

    def test_overwrite_annotations_and_results(self):

        filename = make_temp_file('overwrite.hdf5')

        env = Environment(trajectory='testoverwrite', filename=filename, log_folder=None)

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

        traj = Trajectory(name='Testmigrate', filename=make_temp_file('migrate.hdf5'))

        traj.f_add_result('I.am.a.mean.resu', 42, comment='Test')
        traj.f_add_derived_parameter('ffa', 42)

        traj.f_store()

        new_file = make_temp_file('migrate2.hdf5')
        traj.f_migrate(filename=new_file)

        traj.f_store()

        new_traj = Trajectory()

        new_traj.f_migrate(new_name=traj.v_name, filename=new_file, in_store=True)

        new_traj.v_auto_load=True

        self.assertTrue(new_traj.results.I.am.a.mean.resu == 42)

    def test_wildcard_search(self):

        traj = Trajectory(name='Testwildcard', filename=make_temp_file('wilcard.hdf5'))

        traj.f_add_parameter('expl', 2)
        traj.f_explore({'expl':[1,2,3,4]})

        traj.f_add_result('wc2test.$.hhh', 333)
        traj.f_add_leaf('results.wctest.run_00000000.jjj', 42)
        traj.f_add_result('results.wctest.run_00000001.jjj', 43)

        traj.v_as_run = 1

        self.assertTrue(traj.results.wctest['$'].jjj==43)
        self.assertTrue(traj.results.wc2test.crun.hhh==333)

        traj.f_store()

        print('Removing child1')

        traj.f_remove_child('results', recursive=True)

        print('Doing auto-load')
        traj.v_auto_load = True

        self.assertTrue(traj.results.wctest['$'].jjj==43)
        self.assertTrue(traj.results.wc2test.crun.hhh==333)

        print('Removing child2')

        traj.f_remove_child('results', recursive=True)

        print('auto-loading')
        traj.v_auto_load = True

        self.assertTrue(traj.results.wctest[-2].jjj==43)
        self.assertTrue(traj.results.wc2test[-2].hhh==333)

        print('Removing child3')
        traj.f_remove_child('results', recursive=True)

        print('auto-loading')
        traj.v_auto_load = True

        self.assertTrue(traj.results.wctest[1].jjj==43)
        self.assertTrue(traj.results.wc2test[-1].hhh==333)

        print('Done with wildcard test')

    def test_store_and_load_large_dictionary(self):
        traj = Trajectory(name='Testlargedict', filename=make_temp_file('large_dict.hdf5'))

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

        traj2.f_load(name=traj_name, load_data=2)

        self.compare_trajectories(traj, traj2)


    def test_auto_load(self):


        traj = Trajectory(name='Testautoload', filename=make_temp_file('autoload.hdf5'))

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


        traj = Trajectory(name='Testgetdefault', filename=make_temp_file('autoload.hdf5'))

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
        traj = Trajectory(name='TestVERSION', filename=make_temp_file('testversionmismatch.hdf5'))

        traj.f_add_parameter('group1.test',42)

        traj.f_add_result('testres', 42)

        traj.group1.f_set_annotations(Test=44)

        traj._version='0.1a.1'

        traj.f_store()

        traj2 = Trajectory(name=traj.v_name, add_time=False,
                           filename=make_temp_file('testversionmismatch.hdf5'))

        with self.assertRaises(pex.VersionMismatchError):
            traj2.f_load(load_parameters=2, load_results=2)

        traj2.f_load(load_parameters=2, load_results=2, force=True)

        self.compare_trajectories(traj,traj2)

        print('Mismatch testing done!')

    def test_fail_on_wrong_kwarg(self):
        with self.assertRaises(ValueError):
            filename = 'testsfail.hdf5'
            env = Environment(filename=make_temp_file(filename),
                              log_folder=make_temp_file('logs'),
                          log_stdout=True,
                          logger_names=('STDERROR', 'STDOUT'),
                          foo='bar')

    @unittest.skipIf(platform.system() == 'Windows', 'Log file creation might fail under windows.')
    def test_logging_stdout(self):
        filename = 'teststdoutlog.hdf5'
        filename = make_temp_file(filename)
        env = Environment(filename=filename,
                          log_folder=make_temp_file('logs'),
                          log_stdout=True,
                          logger_names=('STDERR', 'STDOUT'))

        path = env.v_log_path

        mainstr = 'sTdOuTLoGGinG'
        print(mainstr)
        errstr = 'sTdErRLoGGinG'
        sys.stderr.write(errstr)

        mainfilename = os.path.join(path, 'main.txt')
        with open(mainfilename, mode='r') as mainf:
            full_text = mainf.read()

        self.assertTrue(mainstr in full_text)
        self.assertTrue('4444444' not in full_text)
        self.assertTrue('pypet' not in full_text)

        errfilename = os.path.join(path, 'errors_and_warnings.txt')
        with open(errfilename, mode='r') as errf:
            full_text = errf.read()

        self.assertTrue(errstr in full_text)
        self.assertTrue('pypet' not in full_text)

        env.f_disable_logging()

    def test_delete_whole_subtrees(self):
        filename = make_temp_file('testdeltree.hdf5')
        traj = Trajectory(name='TestDelete',
                          filename=filename)

        res = traj.f_add_result('mytest.yourtest.test', a='b', c='d')
        dpar = traj.f_add_derived_parameter('mmm.gr.dpdp', 666)


        res = traj.f_add_result('hhh.ll', a='b', c='d')
        res = traj.f_add_derived_parameter('hhh.gg', 555)

        traj.f_store()

        with ptcompat.open_file(filename) as fh:
            daroot = ptcompat.get_child(fh.root, traj.v_name)
            dpar_table = daroot.overview.derived_parameters_trajectory
            self.assertTrue(len(dpar_table) == 2)
            res_table = daroot.overview.results_trajectory
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

        with ptcompat.open_file(filename) as fh:
            daroot = ptcompat.get_child(fh.root, traj.v_name)
            dpar_table = daroot.overview.derived_parameters_trajectory
            self.assertTrue(len(dpar_table) == 1)
            res_table = daroot.overview.results_trajectory
            self.assertTrue((len(res_table)) == 1)

        traj.f_add_parameter('ggg', 43)
        traj.f_add_parameter('hhh.mmm', 45)
        traj.f_add_parameter('jjj', 55)
        traj.f_add_parameter('hhh.nnn', 55555)

        traj.f_explore({'ggg':[1,2,3]})

        traj.f_store()

        with ptcompat.open_file(filename) as fh:
            daroot = ptcompat.get_child(fh.root, traj.v_name)
            par_table = daroot.overview.parameters
            self.assertTrue(len(par_table) == 4)

        traj.f_delete_item('par.hhh', recursive=True)

        with ptcompat.open_file(filename) as fh:
            daroot = ptcompat.get_child(fh.root, traj.v_name)
            par_table = daroot.overview.parameters
            self.assertTrue(len(par_table) == 2)

        with self.assertRaises(TypeError):
            # We cannot delete something containing an explored parameter
            traj.f_delete_item('par', recursive=True)

        with self.assertRaises(TypeError):
            traj.f_delete_item('ggg')

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

        traj.f_delete_item(res, remove_from_trajectory=True)

        self.assertTrue('results' in traj)
        self.assertTrue(res not in traj)

    def test_throw_warning_if_old_kw_is_used(self):
        pass

        filename = make_temp_file('hdfwarning.hdf5')

        with warnings.catch_warnings(record=True) as w:

            env = Environment(trajectory='test', filename=filename,
                              dynamically_imported_classes=[], log_folder=None)

        with warnings.catch_warnings(record=True) as w:
            traj = Trajectory(dynamically_imported_classes=[])

        traj = env.v_trajectory
        traj.f_store()

        with warnings.catch_warnings(record=True) as w:
            traj.f_load(dynamically_imported_classes=[])

        env.f_disable_logging()

    def test_overwrite_stuff(self):
        traj = Trajectory(name='TestOverwrite', filename=make_temp_file('testowrite.hdf5'))

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
        filename = make_temp_file('asnew.h5')
        traj = Trajectory(name='TestPartial', filename=filename)

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

        self.assertTrue(len(traj) == 3)

        traj.f_shrink()

        self.assertTrue(len(traj) == 1)


    def test_partial_loading(self):
        traj = Trajectory(name='TestPartial', filename=make_temp_file('testpartially.hdf5'))

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

        filename = make_temp_file('hdfsettings.hdf5')
        with Environment('testraj', filename=filename,
                          add_time=True,
                         comment='',
                         dynamic_imports=None,
                         log_folder=None,
                         logger_names=None,
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
                         derived_parameters_per_run=17) as env:

            traj = env.v_trajectory

            traj.f_store()

            hdf5file = pt.openFile(filename=filename)

            table= hdf5file.root._f_getChild(traj.v_name)._f_getChild('overview')._f_getChild('hdf5_settings')

            row = table[0]

            self.assertTrue(row['complevel'] == 4)

            self.assertTrue(row['complib'] == compat.tobytes('zlib'))

            self.assertTrue(row['shuffle'])
            self.assertTrue(row['fletcher32'])
            self.assertTrue(row['pandas_format'] == compat.tobytes('t'))

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

        traj2.f_load(load_parameters=2, load_results=2)

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

        logging.basicConfig(level = logging.INFO)


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

    def test_file_overwriting(self):
        self.traj.f_store()

        with ptcompat.open_file(self.filename, mode='r') as file:
            nchildren = len(file.root._v_children)
            self.assertTrue(nchildren > 0)

        env2 = Environment(filename=self.filename, log_folder=None)
        traj2 = env2.v_trajectory
        traj2.f_store()

        self.assertTrue(os.path.exists(self.filename))

        with ptcompat.open_file(self.filename, mode='r') as file:
            nchildren = len(file.root._v_children)
            self.assertTrue(nchildren > 1)

        env3 = Environment(filename=self.filename, overwrite_file=True, log_folder=None)

        self.assertFalse(os.path.exists(self.filename))

        env2.f_disable_logging()
        env3.f_disable_logging()

    def test_time_display_of_loading(self):
        filename = make_temp_file('sloooow.hdf5')
        log_folder = make_temp_file('logs')
        env = Environment(trajectory='traj', add_time=True, filename=filename,
                          log_stdout=False,
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
        print('Testing large run')
        self.traj.f_add_parameter('TEST', 'test_run')
        ###Explore
        self.explore_large(self.traj)
        self.make_run_large_data()

        # Check if printing and repr work
        print(str(self.env))
        print(repr(self.env))

        newtraj = Trajectory()
        newtraj.f_load(name=self.traj.v_name, as_new=False, load_data=2, filename=self.filename)

        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)

        self.compare_trajectories(self.traj,newtraj)

        size=os.path.getsize(self.filename)
        size_in_mb = size/1000000.
        print('Size is %sMB' % str(size_in_mb))
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
        print('Size is %sMB' % str(size_in_mb))
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
        print('Size is %sMB' % str(size_in_mb))
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

        print('\n $$$$$$$$$$$$$$$$$ Second Run $$$$$$$$$$$$$$$$$$$$$$$$')
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
                          log_stdout=False)

        self.traj = self.env.v_trajectory

        self.traj.f_load(name=traj_name)

        self.expand()

        print('\n $$$$$$$$$$$$ Second Run $$$$$$$$$$ \n')
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

    def tearDown(self):
        self.env.f_disable_logging()
        super(ResultSortTest, self).tearDown()

    def setUp(self):
        self.set_mode()
        logging.basicConfig(level = logging.INFO)

        self.filename = make_temp_file(os.path.join('experiments','tests','HDF5','test.hdf5'))
        self.logfolder = make_temp_file(os.path.join('experiments',
                                                      'tests',
                                                      'Log'))
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

            self.assertTrue(newtraj.z==traj.x*traj.y,' z != x*y: %s != %s * %s' %
                                                  (str(newtraj.z),str(traj.x),str(traj.y)))

        self.assertTrue(traj.v_idx == -1)
        self.assertTrue(traj.v_as_run == None)
        self.assertTrue(newtraj.v_idx == idx)


    def test_expand(self):
        ###Explore
        self.explore(self.traj)

        print(self.env.f_run(multiply))
        traj = self.traj
        self.assertTrue(len(traj) == len(list(compat.listvalues(self.explore_dict)[0])))

        self.traj.f_load_skeleton()
        self.traj.f_load_items(self.traj.f_to_dict().keys(), only_empties=True)
        self.check_if_z_is_correct(traj)

        traj_name = self.env.v_trajectory.v_name
        del self.env
        self.env = Environment(trajectory=self.traj, log_folder=self.logfolder,
                          log_stdout=False)

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
    make_run()