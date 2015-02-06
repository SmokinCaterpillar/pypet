

__author__ = 'Robert Meyer'

import numpy as np
import warnings
import random
from pypet.parameter import Parameter, PickleParameter, ArrayParameter, PickleResult
from pypet.trajectory import Trajectory, load_trajectory
from pypet.utils.explore import cartesian_product
from pypet.environment import Environment
from pypet.storageservice import HDF5StorageService
from pypet import pypetconstants, BaseParameter, BaseResult
import logging
import time
import os
import getopt
import pypet.pypetexceptions as pex

from pypet.tests.test_helpers import make_temp_file, TrajectoryComparator, make_trajectory_name, make_run

import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

class LinkTrajectoryTests(TrajectoryComparator):


    def test_iteration_failure(self):
        traj = Trajectory()

        traj.f_add_parameter_group('test.test3')
        traj.f_add_parameter_group('test2')
        traj.test2.f_add_link(traj.test3)

        with self.assertRaises(pex.NotUniqueNodeError):
            traj.test3

    def test_link_creation(self):

        traj = Trajectory()

        traj.f_add_parameter_group('test.test3')
        traj.f_add_parameter_group('test2')

        with self.assertRaises(ValueError):
            traj.par.f_add_link('test', traj.test2)

        with self.assertRaises(ValueError):
            traj.f_add_link('parameters', traj.test)

        with self.assertRaises(ValueError):
            traj.f_add_link('ps.ss', traj.test)

        with self.assertRaises(ValueError):
            traj.f_add_link('kkkk', PickleResult('fff', 555))

        traj.test.f_add_link('circle1' , traj.test2)
        traj.test2.f_add_link('circle2' , traj.test)

        self.assertTrue(traj.test.circle1.circle2.circle1.circle2 is traj.test)


        traj.f_add_link('hh', traj.test)

        traj.par.f_add_link('overview', traj.test)
        with self.assertRaises(ValueError):
            traj.f_add_link('overview', traj.test)

        with self.assertRaises(ValueError):
            traj.f_add_link('v_crun')

        with self.assertRaises(ValueError):
            traj.par.f_add_link('gg', traj)

        with self.assertRaises(AttributeError):
            traj.f_add_parameter('test.circle1.testy', 33)

        traj.par.f_add_link('gg', traj.circle1)
        self.assertTrue(traj.gg is traj.test2)
        self.assertTrue(traj.test2.test3 is traj.par.test.test3)

        traj.f_add_link(traj.test3)
        self.assertTrue('test3' in traj._links)


    def test_not_getting_links(self):
        traj = Trajectory()

        traj.f_add_parameter_group('test.test3')
        traj.f_add_parameter_group('test2')

        traj.test.f_add_link('circle1' , traj.test2)
        traj.test2.f_add_link('circle2' , traj.test)

        self.assertTrue(traj.test.circle1 is traj.test2)

        traj.v_with_links = False

        with self.assertRaises(AttributeError):
            traj.test.circle1

        found = False
        for item in traj.test.f_iter_nodes(recursive=True, with_links=True):
            if item is traj.test2:
                found=True

        self.assertTrue(found)

        for item in traj.test.f_iter_nodes(recursive=True, with_links=False):
            if item is traj.test2:
                self.assertTrue(False)

        traj.v_with_links=True
        self.assertTrue('circle1' in traj)
        self.assertFalse(traj.f_contains('circle1', with_links=False))

        self.assertTrue('circle1' in traj.test)
        self.assertFalse(traj.test.f_contains('circle1', with_links=False))

        self.assertTrue(traj.test2.test3 is traj.par.test.test3)
        traj.v_with_links = False
        with self.assertRaises(AttributeError):
            traj.test2.test3

        traj.v_with_links = True
        self.assertTrue(traj['test2.test3'] is traj.test3)

        with self.assertRaises(AttributeError):
            traj.f_get('test2.test3', with_links=False)


    def test_link_of_link(self):

        traj = Trajectory()

        traj.f_add_parameter_group('test')
        traj.f_add_parameter_group('test2')

        traj.test.f_add_link('circle1' , traj.test2)
        traj.test2.f_add_link('circle2' , traj.test)
        traj.test.f_add_link('circle2' , traj.test.circle1.circle2)


        self.assertTrue(traj.test.circle2 is traj.test)

    def test_link_removal(self):
        traj = Trajectory()

        traj.f_add_parameter_group('test')
        traj.f_add_parameter_group('test2')

        traj.test.f_add_link('circle1' , traj.test2)
        traj.test2.f_add_link('circle2' , traj.test)

        self.assertTrue('circle1' in traj)
        traj.circle1.circle2.f_remove_link('circle1')
        self.assertTrue('circle1' not in traj.circle2)

        with self.assertRaises(AttributeError):
            traj.test.circle1

        with self.assertRaises(ValueError):
            traj.test.f_remove_link('circle1')

        traj.test2.f_remove_child('circle2')

        self.assertTrue('circle2' not in traj)

    def test_storage_and_loading(self):
        filename = make_temp_file('linktest.hdf5')
        traj = Trajectory(filename=filename)

        traj.f_add_parameter_group('test')
        traj.f_add_parameter_group('test2')
        res= traj.f_add_result('kk', 42)

        traj.par.f_add_link('gg', res)

        traj.f_add_link('hh', res)
        traj.f_add_link('jj', traj.par)
        traj.f_add_link('ii', res)

        traj.test.f_add_link('circle1' , traj.test2)
        traj.test2.f_add_link('circle2' , traj.test)
        traj.test.f_add_link('circle2' , traj.test.circle1.circle2)

        traj.f_add_parameter_group('test.ab.bc.cd')
        traj.cd.f_add_link(traj.test)
        traj.test.f_add_link(traj.cd)

        traj.f_store()

        traj2 = Trajectory(filename=filename)
        traj2.f_load(name=traj.v_name, load_data=2)

        self.assertTrue(traj.kk == traj2.gg, '%s != %s' % (traj.kk, traj2.gg))
        self.assertTrue(traj.cd.test is traj.test)

        self.assertTrue(len(traj._linked_by), len(traj2._linked_by))
        self.compare_trajectories(traj, traj2)

        self.assertTrue('jj' in traj2._nn_interface._nodes_and_leaves)
        self.assertTrue('jj' in traj2._nn_interface._nodes_and_leaves_runs_sorted)
        traj2.f_remove_child('jj')
        self.assertTrue('jj' not in traj2._nn_interface._nodes_and_leaves)
        self.assertTrue('jj' not in traj2._nn_interface._nodes_and_leaves_runs_sorted)
        traj2.f_remove_child('hh')
        traj2.f_remove_child('ii')



        traj2.f_remove_child('parameters', recursive=True)

        traj2.v_auto_load = True

        group = traj2.par.test2.circle2

        self.assertTrue(group is traj2.test)

        retest = traj2.test.circle1

        self.assertTrue(retest is traj2.test2)

        self.assertTrue(traj2.test.circle2 is traj2.test)

        self.assertTrue(traj2.hh == traj2.res.kk)

        traj2.v_auto_load = False
        traj2.f_load_child('jj')
        self.assertTrue(traj2.jj is traj2.par)
        traj2.f_load(load_data=2)
        self.assertTrue(traj2.ii == traj2.res.kk)


    def test_find_in_all_runs_with_links(self):

        traj = Trajectory()

        traj.f_add_parameter('FloatParam')
        traj.par.FloatParam=4.0
        self.explore_dict = {'FloatParam':[1.0,1.1,1.2,1.3]}
        traj.f_explore(self.explore_dict)

        self.assertTrue(len(traj) == 4)

        traj.f_add_result('results.runs.run_00000000.sub.resulttest', 42)
        traj.f_add_result('results.runs.run_00000001.sub.resulttest', 43)
        traj.f_add_result('results.runs.run_00000002.sub.resulttest', 44)

        traj.f_add_result('results.runs.run_00000002.sub.resulttest2', 42)
        traj.f_add_result('results.runs.run_00000003.sub.resulttest2', 43)

        traj.f_add_derived_parameter('derived_parameters.runs.run_00000002.testing', 44)

        res_dict = traj.f_get_from_runs('resulttest', fast_access=True)

        self.assertTrue(len(res_dict)==3)
        self.assertTrue(res_dict['run_00000001']==43)
        self.assertTrue('run_00000003' not in res_dict)

        res_dict = traj.f_get_from_runs(name='sub.resulttest2', use_indices=True)

        self.assertTrue(len(res_dict)==2)
        self.assertTrue(res_dict[3] is traj.f_get('run_00000003.resulttest2'))
        self.assertTrue(1 not in res_dict)

        traj.res.runs.r_0.f_add_link('resulttest2', traj.r_1.f_get('resulttest'))

        res_dict = traj.f_get_from_runs(name='resulttest2', use_indices=True)

        self.assertTrue(len(res_dict)==3)
        self.assertTrue(res_dict[0] is traj.f_get('run_00000001.resulttest'))
        self.assertTrue(1 not in res_dict)

        res_dict = traj.f_get_from_runs(name='resulttest2', use_indices=True, with_links=False)

        self.assertTrue(len(res_dict)==2)
        self.assertTrue(0 not in res_dict)
        self.assertTrue(1 not in res_dict)


    def test_get_all_not_links(self):

        traj = Trajectory()

        traj.f_add_parameter('test.hi', 44)
        traj.f_explore({'hi': [1,2,3]})

        traj.f_add_parameter_group('test.test.test2')
        traj.f_add_parameter_group('test2')
        traj.test2.f_add_link('test', traj.test)

        nodes = traj.f_get_all('par.test')

        self.assertTrue(len(nodes) == 2)

        nodes = traj.f_get_all('par.test', shortcuts=False)

        self.assertTrue(len(nodes) == 1)

        traj.f_set_crun(0)

        traj.f_add_group('f.$.h')
        traj.f_add_group('f.$.g.h')
        traj.f_add_group('f.$.i')
        traj.crun.i.f_add_link('h', traj.crun.h)

        nodes = traj.f_get_all('$.h')

        self.assertTrue(len(nodes)==2)

        nodes = traj.f_get_all('h')

        self.assertTrue(len(nodes)==2)

        traj.v_idx = -1

        nodes = traj.f_get_all('h')

        self.assertTrue(len(nodes)==2)


    def test_links_according_to_run(self):

        traj = Trajectory()

        traj.f_add_parameter('test.hi', 44)
        traj.f_explore({'hi': [1,2,3]})

        traj.f_add_parameter_group('test.test.test2')
        traj.f_add_parameter_group('test2')
        traj.test2.f_add_link('test', traj.test)

        traj.v_idx = 1


    def test_link_deletion(self):
        filename = make_temp_file('linktest2.hdf5')
        traj = Trajectory(filename=filename)

        traj.f_add_parameter_group('test')
        traj.f_add_parameter_group('test2')
        res= traj.f_add_result('kk', 42)
        traj.par.f_add_link('gg', res)

        traj.test.f_add_link('circle1' , traj.test2)
        traj.test2.f_add_link('circle2' , traj.test)

        traj.f_store()

        traj.f_delete_link('par.gg')

        traj2 = Trajectory(filename=filename)
        traj2.f_load(name=traj.v_name, load_data=2)

        with self.assertRaises(AttributeError):
            traj2.gg


def create_link_params(traj):

    traj.f_add_parameter('groupA.groupB.paramA', 5555)
    traj.f_add_parameter('groupC.groupD.paramB', 42)
    traj.par.f_add_link('paraAL', traj.f_get('paramA'))

def explore_params(traj):

    traj.f_explore({'paraAL':[1,2,3,4,5]})

def explore_params2(traj):

    traj.f_explore({'paraAL':[1,6,7,8,9,10,11]})

def dostuff_and_add_links(traj):
    traj.f_add_result('idx', traj.v_idx)
    traj.f_add_result('a.b.c.d', 42)
    traj.res.runs.crun.f_add_link('paraBL', traj.f_get('paramB'))
    traj.res.runs.crun.f_add_link('paraCL', traj.f_get('paramB'))
    traj.res.c.f_add_link('AB', traj.f_get('paramB'))
    traj.f_add_result('x', traj.AB)
    traj.res.f_add_link('$', traj.f_get('paraBL'))


class LinkEnvironmentTest(TrajectoryComparator):
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

    def tearDown(self):
        self.env.f_disable_logging()
        super(LinkEnvironmentTest, self).tearDown()

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
        create_link_params(traj)
        ### Add some parameter:
        explore_params(traj)

        #remember the trajectory and the environment
        self.traj = traj
        self.env = env



    def test_run(self):
        self.env.f_run(dostuff_and_add_links)

        self.traj.f_load(load_data=2)

        traj2 = Trajectory()

        traj2.f_load(name=self.traj.v_name, filename=self.filename)

        traj2.f_load(load_data=2)

        for run in self.traj.f_get_run_names():
            self.assertTrue(self.traj.res.runs[run].paraBL is self.traj.paramB)

        self.compare_trajectories(self.traj, traj2)


class LinkMergeTest(TrajectoryComparator):

    def test_merge_with_linked_derived_parameter(self, disable_logging = True):
        logging.basicConfig(level = logging.INFO)


        self.logfolder = make_temp_file(os.path.join('experiments',
                                                      'tests',
                                                      'Log'))

        random.seed()
        self.trajname1 = 'T1'+ make_trajectory_name(self)
        self.trajname2 = 'T2'+make_trajectory_name(self)
        self.filename = make_temp_file(os.path.join('experiments',
                                                    'tests',
                                                    'HDF5',
                                                    'test%s.hdf5' % self.trajname1))

        self.env1 = Environment(trajectory=self.trajname1, filename=self.filename,
                          file_title=self.trajname1, log_folder=self.logfolder,
                          log_stdout=False)
        self.env2 = Environment(trajectory=self.trajname2, filename=self.filename,
                          file_title=self.trajname2, log_folder=self.logfolder,
                          log_stdout=False)

        self.traj1 = self.env1.v_trajectory
        self.traj2 = self.env2.v_trajectory

        create_link_params(self.traj1)
        create_link_params(self.traj2)

        explore_params(self.traj1)
        explore_params2(self.traj2)

        self.traj1.f_add_derived_parameter('test.$.gg', 42)
        self.traj2.f_add_derived_parameter('test.$.gg', 44)

        self.traj1.f_add_derived_parameter('test.hh.$', 111)
        self.traj2.f_add_derived_parameter('test.hh.$', 53)

        self.env1.f_run(dostuff_and_add_links)
        self.env2.f_run(dostuff_and_add_links)

        old_length = len(self.traj1)

        self.traj1.f_merge(self.traj2, remove_duplicates=True)

        self.traj1.f_load(load_data=2)

        for run in self.traj1.f_get_run_names():
            self.traj1.f_as_run(run)
            idx = self.traj1.v_idx
            param = self.traj1['test.crun.gg']
            if idx < old_length:
                self.assertTrue(param == 42)
            else:
                self.assertTrue(param == 44)

            param = self.traj1['test.hh.crun']
            if idx < old_length:
                self.assertTrue(param == 111)
            else:
                self.assertTrue(param == 53)

        self.assertTrue(len(self.traj1)>old_length)

        for irun in range(len(self.traj1.f_get_run_names())):
            self.assertTrue(self.traj1.res.runs['r_%d' % irun].paraBL == self.traj1.paramB)
            self.assertTrue(self.traj1.res['r_%d' % irun] == self.traj1.paramB)

        if disable_logging:
            self.env1.f_disable_logging()
            self.env2.f_disable_logging()

        return old_length

    def test_remerging(self):
        prev_old_length = self.test_merge_with_linked_derived_parameter(disable_logging=False)

        name = self.traj1

        self.bfilename = make_temp_file(os.path.join('experiments',
                                                     'tests',
                                                     'HDF5',
                                                     'backup_test%s.hdf5' % self.trajname1))

        self.traj1.f_load(load_data=2)

        self.traj1.f_backup(backup_filename=self.bfilename)

        self.traj3 = load_trajectory(index=-1, filename=self.bfilename, load_all=2)

        old_length = len(self.traj1)

        self.traj1.f_merge(self.traj3, backup=False, remove_duplicates=False)

        self.assertTrue(len(self.traj1) > old_length)

        self.traj1.f_load(load_data=2)

        for run in self.traj1.f_get_run_names():
            self.traj1.f_as_run(run)
            idx = self.traj1.v_idx
            param = self.traj1['test.crun.gg']
            if idx < prev_old_length or old_length <= idx < prev_old_length + old_length:
                self.assertTrue(param == 42, '%s != 42' % str(param))
            else:
                self.assertTrue(param == 44, '%s != 44' % str(param))

            param = self.traj1['test.hh.crun']
            if idx < prev_old_length or old_length <= idx < prev_old_length + old_length:
                self.assertTrue(param == 111, '%s != 111' % str(param))
            else:
                self.assertTrue(param == 53, '%s != 53' % str(param))

        self.assertTrue(len(self.traj1)>old_length)

        for irun in range(len(self.traj1.f_get_run_names())):
            self.assertTrue(self.traj1.res.runs['r_%d' % irun].paraBL == self.traj1.paramB)
            self.assertTrue(self.traj1.res['r_%d' % irun] == self.traj1.paramB)

        self.env1.f_disable_logging()
        self.env2.f_disable_logging()


if __name__ == '__main__':
    opt_list, _ = getopt.getopt(sys.argv[1:],'k',['folder='])
    remove = None
    folder = None
    for opt, arg in opt_list:
        if opt == '-k':
            remove = False
            print('I will keep all files.')

        if opt == '--folder':
            folder = arg
            print('I will put all data into folder `%s`.' % folder)

    sys.argv=[sys.argv[0]]
    make_run(remove, folder)