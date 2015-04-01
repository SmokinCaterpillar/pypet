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


from pypet import Environment, Parameter, load_trajectory, cartesian_product, Trajectory

from pypet.tests.testutils.ioutils import make_temp_dir
from pypet.tests.testutils.data import create_param_dict, add_params, simple_calculations

filename = None


def to_test(traj, length):
    for irun in range(length):
        traj._add_run_info(irun)


def test_load():
    newtraj = load_trajectory(index=-1, filename=filename, load_data=1)


if __name__ == '__main__':
    if not os.path.isdir('./tmp'):
        os.mkdir('tmp')
    graphviz = CustomOutput()
    graphviz.output_file = './tmp/traj_add_run_info.png'
    service_filter = GlobbingFilter(include=['*storageservice.*', '*ptcompat.*',
                                             '*naturalnaming.*', '*parameter.*',
                                             '*trajectory.*'])
    # service_filter = GlobbingFilter(include=['*naturalnaming.*', '*trajectory.*'])

    config = Config(groups=True, verbose=True)
    config.trace_filter = service_filter

    print('RUN PROFILE')
    with PyCallGraph(config=config, output=graphviz):
        to_test(Trajectory(), 10000)
    print('DONE RUN PROFILE')
