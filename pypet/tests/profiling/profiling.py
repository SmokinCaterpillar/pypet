__author__ = 'Robert Meyer'

import logging
import os

import numpy as np
import scipy.sparse as spsp
from pycallgraph import PyCallGraph, Config, GlobbingFilter
from pycallgraph.output import GraphvizOutput
from pycallgraph.color import Color


class CustomOutput(GraphvizOutput):
    def node_color(self, node):
        value = float(node.time.fraction)
        return Color.hsv(value / 2 + .5, value, 0.9)

    def edge_color(self, edge):
        value = float(edge.time.fraction)
        return Color.hsv(value / 2 + .5, value, 0.7)


from pypet import Environment, Parameter, load_trajectory, cartesian_product

from pypet.tests.testutils.ioutils import make_temp_dir
from pypet.tests.testutils.data import create_param_dict, add_params, simple_calculations

filename = None


def explore(traj):
    explored ={'Normal.trial': [0],
        'Numpy.double': [np.array([1.0,2.0,3.0,4.0]), np.array([-1.0,3.0,5.0,7.0])],
        'csr_mat' :[spsp.csr_matrix((2222,22)), spsp.csr_matrix((2222,22))]}

    explored['csr_mat'][0][1,2]=44.0
    explored['csr_mat'][1][2,2]=33

    traj.f_explore(cartesian_product(explored))


def test_run():

    global filename


    np.random.seed()
    trajname = 'profiling'
    filename = make_temp_dir(os.path.join('hdf5', 'test%s.hdf5' % trajname))

    env = Environment(trajectory=trajname, filename=filename,
                      file_title=trajname,
                      log_stdout=False,
                      results_per_run=5,
                      derived_parameters_per_run=5,
                      multiproc=False,
                      ncores=1,
                      wrap_mode='LOCK',
                      use_pool=False,
                      overwrite_file=True)

    traj = env.v_trajectory

    traj.v_standard_parameter=Parameter

    ## Create some parameters
    param_dict={}
    create_param_dict(param_dict)
    ### Add some parameter:
    add_params(traj,param_dict)

    #remember the trajectory and the environment
    traj = traj
    env = env

    traj.f_add_parameter('TEST', 'test_run')
    ###Explore
    explore(traj)

    ### Make a test run
    simple_arg = -13
    simple_kwarg= 13.0
    env.f_run(simple_calculations,simple_arg,simple_kwarg=simple_kwarg)

    size=os.path.getsize(filename)
    size_in_mb = size/1000000.
    print('Size is %sMB' % str(size_in_mb))


def test_load():
    newtraj = load_trajectory(index=-1, filename=filename, load_data=1)


if __name__ == '__main__':
    if not os.path.isdir('./tmp'):
        os.mkdir('tmp')
    graphviz = CustomOutput()
    graphviz.output_file = './tmp/run_profile_traj_slots.png'
    # service_filter = GlobbingFilter(include=['*storageservice.*', '*ptcompat.*',
    #                                          '*naturalnaming.*', '*parameter.*',
    #                                          '*trajectory.*'])
    service_filter = GlobbingFilter(include=['*naturalnaming.*', '*trajectory.*'])

    config = Config(groups=True, verbose=True)
    config.trace_filter = service_filter

    print('RUN PROFILE')
    with PyCallGraph(config=config, output=graphviz):
        test_run()
    print('DONE RUN PROFILE')

    graphviz = CustomOutput()
    graphviz.output_file = './tmp/load_mode_1_profile_traj_slots.png'

    print('LOAD PROFILE')
    with PyCallGraph(config=config, output=graphviz):
        test_load()
    print('DONE LOAD PROFILE')