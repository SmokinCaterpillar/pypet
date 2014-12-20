

__author__ = 'Robert Meyer'

import numpy as np
import warnings
from pypet.parameter import Parameter, PickleParameter, ArrayParameter, PickleResult
from pypet.trajectory import Trajectory
from pypet.utils.explore import cartesian_product
from pypet.environment import Environment
from pypet.storageservice import HDF5StorageService
from pypet import pypetconstants, BaseParameter, BaseResult
import logging
import pypet.pypetexceptions as pex

from pypet.tests.test_helpers import make_temp_file, TrajectoryComparator

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

        traj.f_store()

        traj2 = Trajectory(filename=filename)
        traj2.f_load(name=traj.v_name, load_all=2)

        self.assertTrue(traj.kk == traj2.gg, '%s != %s' % (traj.kk, traj2.gg))

        self.assertTrue(len(traj._linked_by), len(traj2._linked_by))
        self.compare_trajectories(traj, traj2)

    def test_link_deletion(self):
        filename = make_temp_file('linktest.hdf5')
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