

__author__ = 'Robert Meyer'

import random
import logging
import os
import getopt
import sys

from pypet.parameter import Parameter
from pypet.trajectory import Trajectory, load_trajectory
from pypet.environment import Environment
from pypet.tests.testutils.ioutils import make_temp_dir, make_trajectory_name, run_suite, \
     parse_args, get_log_config
from pypet.tests.testutils.data import TrajectoryComparator


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

    tags = 'integration', 'hdf5', 'environment', 'links'

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

    def tearDown(self):
        self.env.f_disable_logging()
        super(LinkEnvironmentTest, self).tearDown()

    def setUp(self):
        self.set_mode()

        logging.basicConfig(level=logging.ERROR)


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

    tags = 'integration', 'hdf5', 'environment', 'links', 'merge'

    def test_merge_with_linked_derived_parameter(self, disable_logging = True):
        logging.basicConfig(level = logging.ERROR)


        self.logfolder = make_temp_dir(os.path.join('experiments',
                                                      'tests',
                                                      'Log'))

        random.seed()
        self.trajname1 = 'T1'+ make_trajectory_name(self)
        self.trajname2 = 'T2'+make_trajectory_name(self)
        self.filename = make_temp_dir(os.path.join('experiments',
                                                    'tests',
                                                    'HDF5',
                                                    'test%s.hdf5' % self.trajname1))

        self.env1 = Environment(trajectory=self.trajname1, filename=self.filename,
                          file_title=self.trajname1,

                          log_stdout=False, log_config=get_log_config())
        self.env2 = Environment(trajectory=self.trajname2, filename=self.filename,
                          file_title=self.trajname2,

                          log_stdout=False, log_config=get_log_config())

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
            self.traj1.v_crun = run
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

        self.assertTrue(len(self.traj1) > old_length)

        for irun in range(len(self.traj1.f_get_run_names())):
            self.assertTrue(self.traj1.res['r_%d' % irun] == self.traj1.paramB)
            self.assertTrue(self.traj1.res.runs['r_%d' % irun].paraBL == self.traj1.paramB)

        if disable_logging:
            self.env1.f_disable_logging()
            self.env2.f_disable_logging()

        return old_length

    def test_remerging(self):
        prev_old_length = self.test_merge_with_linked_derived_parameter(disable_logging=False)

        name = self.traj1

        self.bfilename = make_temp_dir(os.path.join('experiments',
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
            self.traj1.v_crun = run
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
    opt_args = parse_args()
    run_suite(**opt_args)