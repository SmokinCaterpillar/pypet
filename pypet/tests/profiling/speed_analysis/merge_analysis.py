__author__ = 'robert'

import numpy as np
from pypet.parameter import Parameter
from pypet.utils.explore import cartesian_product
from pypet.environment import Environment
from pypet import pypetconstants
import logging
import os
import time
from scipy.stats import pearsonr

import numpy as np
import scipy.sparse as spsp
from pycallgraph import PyCallGraph, Config, GlobbingFilter
from pycallgraph.output import GraphvizOutput
from pycallgraph.color import Color
import unittest

from pypet.tests.testutils.ioutils import run_suite, make_temp_dir, make_trajectory_name, \
     parse_args, get_log_config
from pypet.tests.testutils.data import add_params, simple_calculations, TrajectoryComparator,\
    multiply, create_param_dict
from pypet.tests.integration.environment_test import my_set_func, my_run_func


class CustomOutput(GraphvizOutput):
    def node_color(self, node):
        value = float(node.time.fraction)
        return Color.hsv(value / 2 + .5, value, 0.9)

    def edge_color(self, edge):
        value = float(edge.time.fraction)
        return Color.hsv(value / 2 + .5, value, 0.7)


class TestConsecutiveMerges(TrajectoryComparator):

    tags = 'integration', 'hdf5', 'environment', 'merge', 'consecutive_merge'

    def check_if_z_is_correct(self,traj):
        for x in range(len(traj)):
            traj.v_idx=x

            self.assertTrue(traj.crun.z==traj.x*traj.y,' z != x*y: %s != %s * %s' %
                                                  (str(traj.crun.z),str(traj.x),str(traj.y)))
        traj.v_idx=-1

    def set_mode(self):
        self.mode = 'LOCK'
        self.multiproc = False
        self.ncores = 1
        self.use_pool=True
        self.log_stdout=False
        self.freeze_input=False

    def explore(self,traj):
        self.explore_dict={'x':range(10),'y':range(10)}
        traj.f_explore(self.explore_dict)

    def setUp(self):
        self.envs = []
        self.trajs = []
        self.set_mode()

        self.filename = make_temp_dir(os.path.join('experiments','tests','HDF5','test.hdf5'))

        self.trajname = make_trajectory_name(self)

    def _make_env(self, idx):
       return Environment(trajectory=self.trajname+str(idx),filename=self.filename,
                          file_title=self.trajname,
                          log_stdout=False,
                          log_config=get_log_config(),
                          multiproc=self.multiproc,
                          wrap_mode=self.mode,
                          ncores=self.ncores)

    @staticmethod
    def strictly_increasing(L):
        return all(x<y for x, y in zip(L, L[1:]))

    def test_consecutive_merges(self):

        ntrajs = 41
        for irun in range(ntrajs):
            self.envs.append(self._make_env(irun))
            self.trajs.append(self.envs[-1].v_traj)
            self.trajs[-1].f_add_parameter('x',0)
            self.trajs[-1].f_add_parameter('y',0)
            self.explore(self.trajs[-1])

        timings = []
        for irun in range(ntrajs):
            self.envs[irun].f_run(multiply)
            start = time.time()
            # self.trajs[irun].f_load_skeleton()
            # end = time.time()
            # delta = end -start
            # timings.append(delta)
        print timings

        merge_traj = self.trajs[0]
        merge_traj.f_load_skeleton()

        timings = []

        for irun in range(1, ntrajs):
            start = time.time()
            if False and (irun == ntrajs -1 or irun == 1):
                if not os.path.isdir('./tmp'):
                    os.mkdir('tmp')
                graphviz = CustomOutput()
                graphviz.output_file = './tmp/merge_nskelteon_%d.png' % irun
                # service_filter = GlobbingFilter(include=['*storageservice.*', '*ptcompat.*',
                #                                          '*naturalnaming.*', '*parameter.*',
                #                                          '*trajectory.*'])
                service_filter = GlobbingFilter(include=['*trajectory.*', '*storageservice.*'])
                config = Config(groups=True, verbose=True)
                config.trace_filter = service_filter
                print('RUN MERGE')
                with PyCallGraph(config=config, output=graphviz):
                    merge_traj.f_merge(self.trajs[irun], backup=False, consecutive_merge=True,
                                       delete_other_trajectory=True)
                print('DONE MERGING')
            else:
                merge_traj.f_merge(self.trajs[irun], backup=False, consecutive_merge=True,
                                   delete_other_trajectory=True)
            end = time.time()
            delta = end -start
            timings.append(delta)

        print(timings)
        # # Test if there is no linear dependency for consecutive merges:
        # if self.strictly_increasing(timings) and len(timings) > 1:
        #     raise ValueError('Timings %s are strictly increasing' % str(timings))
        # r, alpha = pearsonr(range(len(timings)), timings)
        # logging.error('R and Alpha of consecutive merge test %s' % str((r,alpha)))
        # if alpha < 0.01:
        #     raise ValueError( 'R and Alpha of consecutive merge test %s\n' % str((r,alpha)),
        #         'Timings %s are lineary increasing' % str(timings))

        merge_traj.f_store()
        merge_traj.f_load(load_data=2)
        self.check_if_z_is_correct(merge_traj)

    def tearDown(self):
        for env in self.envs:
            env.f_disable_logging()

unittest.main(verbosity=2)