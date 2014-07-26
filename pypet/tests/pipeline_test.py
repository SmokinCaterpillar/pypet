__author__ = 'Robert Meyer'


from pypet.trajectory import Trajectory
from pypet.utils.explore import cartesian_product
from pypet.environment import Environment
from pypet import pypetconstants
from pypet.parameter import Parameter
import logging
import multiprocessing as mp
import pickle

import os

import tables as pt
from pypet.tests.test_helpers import add_params, simple_calculations, create_param_dict, make_run, \
    TrajectoryComparator, make_temp_file, multiply

class Multiply(object):

    def __init__(self):
        self.var=42

    def __call__(self, traj, i):
        z = traj.x * traj.y + i
        traj.f_add_result('z', z)
        return z

class CustomParameter(Parameter):

    def __init__(self, *args, **kwargs):
        super(CustomParameter, self).__init__(*args, **kwargs)

def postproc(traj, results, idx):
    print(idx)

    traj.f_update_skeleton()

    if len(results) <= 4 and len(traj) == 4:
        return {'x':[1,2], 'y':[1,2]}
    if len(results) <= 6 and len(traj) == 6:
        traj.f_expand({'x':[2,3], 'y':[0,1]})

def mypipeline(traj):

    traj.f_add_parameter('x', 1, comment='1st')
    traj.f_add_parameter('y', 1, comment='1st')

    exp_dict = {'x':[1, 2, 3, 4],
                     'y':[1, 2, 3, 4]}

    traj.f_explore(exp_dict)

    return (Multiply(), (22,)), (postproc, (42,))


class TestPostProc(TrajectoryComparator):

    def setUp(self):

        self.env_kwargs={}

    def make_environment(self, filename, trajname='Test', **kwargs):

        #self.filename = '../../experiments/tests/HDF5/test.hdf5'
        filename = make_temp_file(filename)
        logfolder = make_temp_file('experiments/tests/Log')
        cntfolder = make_temp_file('experiments/tests/cnt/')

        env = Environment(trajectory=trajname,
                          dynamically_imported_classes=[CustomParameter],
                          filename=filename, log_folder=logfolder, log_stdout=False,
                          **self.env_kwargs)

        return env, filename, logfolder, cntfolder


    def test_postprocessing(self):

        filename = 'testpostproc.hdf5'
        env1 = self.make_environment(filename, 'k1')[0]
        env2 = self.make_environment(filename, 'k2')[0]

        traj1 = env1.v_trajectory
        traj2 = env2.v_trajectory

        trajs = [traj1, traj2]

        for traj in trajs:
            traj.f_add_parameter('x', 1, comment='1st')
            traj.f_add_parameter('y', 1, comment='1st')

        exp_dict2 = {'x':[1, 2, 3, 4, 1, 2, 2, 3],
                     'y':[1, 2, 3, 4, 1, 2, 0, 1]}

        traj2.f_explore(exp_dict2)

        exp_dict1 = {'x':[1, 2, 3, 4],
                     'y':[1, 2, 3, 4]}

        traj1.f_explore(exp_dict1)

        env2.f_run(Multiply(), 22)

        env1.f_add_postprocessing(postproc, 42)

        env1.f_run(Multiply(), 22)

        traj1.f_load(load_all = 2)
        traj2.f_load(load_all = 2)

        self.compare_trajectories(traj1, traj2)


    def test_pipeline(self):

        filename = 'testpostprocpipe.hdf5'
        env1 = self.make_environment(filename, 'k1')[0]
        env2 = self.make_environment(filename, 'k2')[0]

        traj1 = env1.v_trajectory
        traj2 = env2.v_trajectory

        trajs = [traj1, traj2]


        traj2.f_add_parameter('x', 1, comment='1st')
        traj2.f_add_parameter('y', 1, comment='1st')

        exp_dict2 = {'x':[1, 2, 3, 4, 1, 2, 2, 3],
                     'y':[1, 2, 3, 4, 1, 2, 0, 1]}

        traj2.f_explore(exp_dict2)


        env1.f_pipeline(pipeline=mypipeline)

        env2.f_run(Multiply(), 22)

        traj1.f_load(load_all = 2)
        traj2.f_load(load_all = 2)

        self.compare_trajectories(traj1, traj2)



class TestMPPostProc(TestPostProc):

    def setUp(self):
        self.env_kwargs={'multiproc':True, 'ncores': 3}



class TestMPImmediatePostProc(TestPostProc):

    def setUp(self):
        self.env_kwargs={'multiproc':True, 'ncores': 2, 'immediate_postproc' : True}



if __name__ == '__main__':
    make_run()