__author__ = 'Robert Meyer'

import os
import logging
import platform

from pypet.tests.testutils.ioutils import unittest
from pypet.trajectory import Trajectory
from pypet.environment import Environment
from pypet.parameter import Parameter
from pypet.tests.testutils.ioutils import run_suite, make_temp_dir,  \
    get_root_logger, parse_args, get_log_config
from pypet.tests.testutils.data import TrajectoryComparator
from pypet.utils.mpwrappers import QueueStorageServiceSender, PipeStorageServiceSender, LockWrapper, \
    ReferenceWrapper
import time

class Multiply(object):

    def __init__(self):
        self.var=42

    def __call__(self, traj, i, w=0):
        if traj.v_idx == 0:
            # to shuffle results
            time.sleep(0.2)
        z = traj.x * traj.y + i + w
        zres = traj.f_add_result('z', z)
        g=traj.res.f_add_group('I.link.to.$')
        g.f_add_link('z', zres)
        if 'jjj.kkk' not in traj:
            h = traj.res.f_add_group('jjj.kkk')
        else:
            h = traj.jjj.kkk
        h.f_add_link('$', zres)
        return z


class CustomParameter(Parameter):

    def __init__(self, *args, **kwargs):
        super(CustomParameter, self).__init__(*args, **kwargs)

def postproc(traj, results, idx):
    get_root_logger().info(idx)

    if isinstance(traj.v_storage_service, (LockWrapper, ReferenceWrapper)):
        traj.f_load_skeleton()

    if isinstance(traj.v_storage_service, (QueueStorageServiceSender, PipeStorageServiceSender)):
        try:
            traj.f_load()
            raise RuntimeError('Should not load')
        except NotImplementedError:
            pass

    if len(results) <= 4 and len(traj) == 4:
        return {'x':[1,2], 'y':[1,2]}
    if len(results) <= 6 and len(traj) == 6:
        traj.f_expand({'x':[2,3], 'y':[0,1]})

def postproc_with_iter_args(traj, results, idx):
    get_root_logger().info(idx)

    if isinstance(traj.v_storage_service, (LockWrapper, ReferenceWrapper)):
        traj.f_load_skeleton()

    if len(results) <= 4 and len(traj) == 4:
        assert idx == 42
        return {'x':[1,2], 'y':[1,2]}, ([5,6],), {'w':[7,8]}, (43,)
    if len(results) <= 6 and len(traj) == 6:
        assert idx == 43
        traj.f_expand({'x':[2,3], 'y':[0,1]})
        return {}, ([7,8],), {'w':[9,10]}

def mypipelin_with_iter_args(traj):

    traj.f_add_parameter('x', 1, comment='1st')
    traj.f_add_parameter('y', 1, comment='1st')

    exp_dict = {'x':[1, 2, 3, 4],
                     'y':[1, 2, 3, 4]}

    traj.f_explore(exp_dict)

    return (Multiply(), ([22,23,24,25],), {'w': [5,6,7,8] }), (postproc_with_iter_args, (42,))

def mypipeline(traj):

    traj.f_add_parameter('x', 1, comment='1st')
    traj.f_add_parameter('y', 1, comment='1st')

    exp_dict = {'x':[1, 2, 3, 4],
                     'y':[1, 2, 3, 4]}

    traj.f_explore(exp_dict)

    return (Multiply(), (22,)), (postproc, (42,))


class TestPostProc(TrajectoryComparator):

    tags = 'integration', 'hdf5', 'environment', 'postproc'

    def setUp(self):

        self.env_kwargs={'add_time': True}

    def make_environment(self, filename, trajname='Test', log=True, **kwargs):

        #self.filename = '../../experiments/tests/HDF5/test.hdf5'
        filename = make_temp_dir(filename)
        logfolder = make_temp_dir(os.path.join('experiments',
                                                      'tests',
                                                      'Log'))
        cntfolder = make_temp_dir(os.path.join('experiments',
                                                      'tests',
                                                      'cnt'))
        if log:
            log_config = get_log_config()
        else:
            log_config = None
        env = Environment(trajectory=trajname,
                          # log_levels=logging.INFO,
                          # log_config=None,
                          log_config=log_config,
                          dynamic_imports=[CustomParameter],
                          filename=filename, log_stdout=False,
                          **self.env_kwargs)

        return env, filename, logfolder, cntfolder

    def test_postprocessing(self):

        filename = 'testpostproc.hdf5'
        env1 = self.make_environment(filename, 'k1')[0]
        env2 = self.make_environment(filename, 'k2', log=False)[0]

        traj1 = env1.v_trajectory
        traj2 = env2.v_trajectory

        trajs = [traj1, traj2]

        traj1.f_add_result('test.run_00000000.f', 555)
        traj2.f_add_result('test.run_00000000.f', 555)
        traj1.f_add_link('linking', traj1.f_get('f'))
        traj2.f_add_link('linking', traj2.f_get('f'))

        for traj in trajs:
            traj.f_add_parameter('x', 1, comment='1st')
            traj.f_add_parameter('y', 1, comment='2nd')

        exp_dict2 = {'x':[1, 2, 3, 4, 1, 2, 2, 3],
                     'y':[1, 2, 3, 4, 1, 2, 0, 1]}

        traj2.f_explore(exp_dict2)

        exp_dict1 = {'x':[1, 2, 3, 4],
                     'y':[1, 2, 3, 4]}

        traj1.f_explore(exp_dict1)

        env2.f_run(Multiply(), 22)

        env1.f_add_postprocessing(postproc, 42)

        env1.f_run(Multiply(), 22)

        traj1.f_load(load_data=2)
        traj2.f_load(load_data=2)

        self.compare_trajectories(traj1, traj2)

        env1.f_disable_logging()
        env2.f_disable_logging()

    def test_postprocessing_iter_args(self):

        filename = 'testpostproc.hdf5'
        env1 = self.make_environment(filename, 'k1')[0]
        env2 = self.make_environment(filename, 'k2', log=False)[0]

        traj1 = env1.v_trajectory
        traj2 = env2.v_trajectory

        trajs = [traj1, traj2]

        traj1.f_add_result('test.run_00000000.f', 555)
        traj2.f_add_result('test.run_00000000.f', 555)
        traj1.f_add_link('linking', traj1.f_get('f'))
        traj2.f_add_link('linking', traj2.f_get('f'))

        for traj in trajs:
            traj.f_add_parameter('x', 1, comment='1st')
            traj.f_add_parameter('y', 1, comment='2nd')

        exp_dict2 = {'x':[1, 2, 3, 4, 1, 2, 2, 3],
                     'y':[1, 2, 3, 4, 1, 2, 0, 1]}

        traj2.f_explore(exp_dict2)

        exp_dict1 = {'x':[1, 2, 3, 4],
                     'y':[1, 2, 3, 4]}

        traj1.f_explore(exp_dict1)

        env2.f_run_map(Multiply(), [22,23,24,25,5,6,7,8], w=[5,6,7,8,7,8,9,10])

        env1.f_add_postprocessing(postproc_with_iter_args, 42)

        env1.f_run_map(Multiply(), [22,23,24,25], w=[5,6,7,8])

        traj1.f_load(load_data=2)
        traj2.f_load(load_data=2)

        self.compare_trajectories(traj1, traj2)

        env1.f_disable_logging()
        env2.f_disable_logging()


    def test_pipeline(self):

        filename = 'testpostprocpipe.hdf5'
        env1, filename, _, _ = self.make_environment(filename, 'k1')
        env2 = self.make_environment(filename, 'k2', log=False)[0]

        traj1 = env1.v_trajectory
        traj2 = env2.v_trajectory

        trajs = [traj1, traj2]


        traj2.f_add_parameter('x', 1, comment='1st')
        traj2.f_add_parameter('y', 1, comment='1st')

        exp_dict2 = {'x':[1, 2, 3, 4, 1, 2, 2, 3],
                     'y':[1, 2, 3, 4, 1, 2, 0, 1]}

        traj2.f_explore(exp_dict2)


        res1 = env1.pipeline(pipeline=mypipeline)

        self.are_results_in_order(res1)

        res2 = env2.f_run(Multiply(), 22)

        self.are_results_in_order(res2)

        traj_name = traj1.v_name
        traj1 = Trajectory(traj_name, add_time=False, filename=filename)

        traj1.f_load(load_data=2)
        traj2.f_load(load_data=2)

        self.compare_trajectories(traj1, traj2)

        env1.f_disable_logging()
        env2.f_disable_logging()

    def test_pipeline_with_iter_args(self):

        filename = 'testpostprocpipe.hdf5'
        env1 = self.make_environment(filename, 'k1')[0]
        env2 = self.make_environment(filename, 'k2', log=False)[0]

        traj1 = env1.v_trajectory
        traj2 = env2.v_trajectory

        trajs = [traj1, traj2]


        traj2.f_add_parameter('x', 1, comment='1st')
        traj2.f_add_parameter('y', 1, comment='1st')

        exp_dict2 = {'x':[1, 2, 3, 4, 1, 2, 2, 3],
                     'y':[1, 2, 3, 4, 1, 2, 0, 1]}

        traj2.f_explore(exp_dict2)


        res1 = env1.pipeline_map(pipeline=mypipelin_with_iter_args)

        self.are_results_in_order(res1)

        res2 = env2.f_run_map(Multiply(), [22,23,24,25,5,6,7,8], w=[5,6,7,8,7,8,9,10])

        self.are_results_in_order(res2)

        traj1.f_load(load_data=2)
        traj2.f_load(load_data=2)

        self.compare_trajectories(traj1, traj2)

        env1.f_disable_logging()
        env2.f_disable_logging()


class TestMPPostProc(TestPostProc):

    tags = 'integration', 'hdf5', 'environment', 'postproc', 'multiproc'

    def setUp(self):
        self.env_kwargs={'multiproc':True, 'ncores': 3, 'add_time': True}


class TestMPImmediatePostProcLock(TestPostProc):

    tags = 'integration', 'hdf5', 'environment', 'postproc', 'multiproc', 'lock'

    def setUp(self):
        self.env_kwargs={'multiproc':True, 'ncores': 2, 'immediate_postproc' : True,
                         'add_time': True}


class TestMPImmediatePostProcQueue(TestPostProc):

    tags = 'integration', 'hdf5', 'environment', 'postproc', 'multiproc', 'queue'

    def setUp(self):
        self.env_kwargs={'multiproc':True, 'ncores': 2, 'immediate_postproc' : True,
                         'wrap_mode': 'QUEUE', 'add_time': True}


class TestMPImmediatePostProcLocal(TestPostProc):

    tags = 'integration', 'hdf5', 'environment', 'postproc', 'multiproc', 'local'

    def setUp(self):
        self.env_kwargs={'multiproc':True, 'ncores': 2, 'immediate_postproc' : True,
                         'wrap_mode': 'LOCAL', 'add_time': True}


@unittest.skipIf(platform.system() == 'Windows', 'Pipes cannot be pickled!')
class TestMPImmediatePostProcPipe(TestPostProc):

    tags = 'integration', 'hdf5', 'environment', 'postproc', 'multiproc', 'pipe'

    def setUp(self):
        self.env_kwargs={'multiproc':True, 'ncores': 2, 'immediate_postproc' : True,
                         'wrap_mode': 'PIPE', 'add_time': True}


if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)