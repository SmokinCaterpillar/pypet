

__author__ = 'Robert Meyer'

import numpy as np
import warnings
import random
from pypet.parameter import Parameter, PickleParameter, ArrayParameter, PickleResult
from pypet.trajectory import Trajectory
from pypet.utils.explore import cartesian_product
from pypet.environment import Environment
from pypet.storageservice import HDF5StorageService
from pypet import pypetconstants, BaseParameter, BaseResult
import logging
import pypet.pypetexceptions as pex

from pypet.tests.test_helpers import make_temp_file, TrajectoryComparator, make_trajectory_name

import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

class LinkTrajectoryTests(TrajectoryComparator):

    def test_link_creation(self):
        traj = Trajectory()

        traj.f_add_parameter_group('test')
        traj.f_add_parameter_group('test2')

        with self.assertRaises(ValueError):
            traj.par.f_add_link('test', traj.test2)

        traj.test.f_add_link('circle1' , traj.test2)
        traj.test2.f_add_link('circle2' , traj.test)

        self.assertTrue(traj.test.circle1.circle2.circle1.circle2 is traj.test)

        with self.assertRaises(ValueError):
            traj.f_add_link('gg', traj.test)

        with self.assertRaises(ValueError):
            traj.par.f_add_link('gg', traj)

        with self.assertRaises(AttributeError):
            traj.f_add_parameter('test.circle1.testy', 33)

        traj.par.f_add_link('gg', traj.circle1)
        self.assertTrue(traj.gg is traj.test2)

    def test_link_removal(self):
        traj = Trajectory()

        traj.f_add_parameter_group('test')
        traj.f_add_parameter_group('test2')

        traj.test.f_add_link('circle1' , traj.test2)
        traj.test2.f_add_link('circle2' , traj.test)

        traj.circle1.circle2.f_remove_link('circle1')

        with self.assertRaises(AttributeError):
            traj.test.circle1

        with self.assertRaises(ValueError):
            traj.test.f_remove_link('circle1')

    def test_storage_and_loading(self):
        filename = make_temp_file('linktest.hdf5')
        traj = Trajectory(filename=filename)

        traj.f_add_parameter_group('test')
        traj.f_add_parameter_group('test2')
        res= traj.f_add_result('kk', 42)

        traj.par.f_add_link('gg', res)

        traj.test.f_add_link('circle1' , traj.test2)
        traj.test2.f_add_link('circle2' , traj.test)

        traj.f_add_parameter_group('test.ab.bc.cd')
        traj.cd.f_add_link(traj.test)
        traj.test.f_add_link(traj.cd)

        traj.f_store()

        traj2 = Trajectory(filename=filename)
        traj2.f_load(name=traj.v_name, load_all=2)

        self.assertTrue(traj.kk == traj2.gg, '%s != %s' % (traj.kk, traj2.gg))
        self.assertTrue(traj.cd.test is traj.test)

        self.assertTrue(len(traj._linked_by), len(traj2._linked_by))
        self.compare_trajectories(traj, traj2)

        traj2.f_remove_child('parameters', recursive=True)

        traj2.v_auto_load = True

        group = traj2.par.test2.circle2

        self.assertTrue(group is traj2.test)

        retest = traj2.test.circle1

        self.assertTrue(retest is traj2.test2)

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
        traj2.f_load(name=traj.v_name, load_all=2)

        with self.assertRaises(AttributeError):
            traj2.gg


def create_link_params(traj):

    traj.f_add_parameter('groupA.groupB.paramA', 5555)
    traj.f_add_parameter('groupC.groupD.paramB', 42)
    traj.par.f_add_link('paraAL', traj.f_get('paramA'))

def explore_params(traj):

    traj.f_explore({'paraAL':[1,2,3,4,5]})

def dostuff_and_add_links(traj):
    traj.f_add_result('idx', traj.v_idx)
    traj.res.runs.crun.f_add_link('paraBL', traj.f_get('paramB'))

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
        create_link_params(traj)
        ### Add some parameter:
        explore_params(traj)

        #remember the trajectory and the environment
        self.traj = traj
        self.env = env


    def test_run(self):
        self.env.f_run(dostuff_and_add_links)

        self.traj.f_load(load_all=2)

        traj2 = Trajectory()

        traj2.f_load(name=self.traj.v_name, filename=self.filename)

        traj2.f_load(load_all=2)

        for run in self.traj.f_get_run_names():
            self.assertTrue(self.traj.res.runs[run].paraBL is self.traj.paramB)

        self.compare_trajectories(self.traj, traj2)