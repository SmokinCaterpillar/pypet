__author__ = 'robert'



from pypet import Environment, Trajectory
from pypet.tests.testutils.ioutils import make_temp_dir, get_log_config
import os
import matplotlib.pyplot as plt
import numpy as np
import time

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

def job(traj):
    traj.f_ares('$set.$', 42, comment='A result')



def get_runtime(length):
    filename = os.path.join('tmp', 'hdf5', 'many_runs.hdf5')

    with Environment(filename = filename,
                      log_levels=20, report_progress=(0.0000002, 'progress', 50),
                      overwrite_file=True, purge_duplicate_comments=False,
                      log_stdout=False,
                      summary_tables=False, small_overview_tables=False) as env:

        traj = env.v_traj

        traj.par.f_apar('x', 0, 'parameter')

        traj.f_explore({'x': range(length)})

        max_run = 100

        for idx in range(len(traj)):
            if idx > max_run:
                traj.f_get_run_information(idx, copy=False)['completed'] = 1
        traj.f_store()

        if not os.path.isdir('./tmp'):
            os.mkdir('tmp')
        graphviz = CustomOutput()
        graphviz.output_file = './tmp/run_profile_storage_%d.png' % len(traj)
        service_filter = GlobbingFilter(include=['*storageservice.*'])

        config = Config(groups=True, verbose=True)
        config.trace_filter = service_filter


        print('RUN PROFILE')
        with PyCallGraph(config=config, output=graphviz):
            # start = time.time()
            # env.f_run(job)
            # end = time.time()
            for irun in range(100):
                traj._make_single_run(irun+len(traj)/2)
                # Measure start time
                traj._set_start()
                traj.f_ares('$set.$', 42, comment='A result')
                traj._set_finish()
                traj._store_final(store_data=2)
                traj._finalize_run()
            print('STARTING_to_PLOT')
        print('DONE RUN PROFILE')


        # dicts = [traj.f_get_run_information(x) for x in range(min(len(traj), max_run))]
    # total = end - start
    # return total/float(min(len(traj), max_run)), total/float(min(len(traj), max_run)) * len(traj)

def main():
    lengths = [1000, 1000000]
    runtimes = [get_runtime(x) for x in lengths]
    # avg_runtimes = [x[0] for x in runtimes]
    # summed_runtime = [x[1] for x in runtimes]

    # plt.subplot(2, 1, 1)
    # plt.semilogx(list(reversed(lengths)), list(reversed(avg_runtimes)), linewidth=2)
    # plt.xlabel('Runs')
    # plt.ylabel('t[s]')
    # plt.title('Average Runtime per single run')
    # plt.grid()
    # plt.subplot(2, 1, 2)
    # plt.loglog(lengths, summed_runtime, linewidth=2)
    # plt.grid()
    # plt.xlabel('Runs')
    # plt.ylabel('t[s]')
    # plt.title('Total runtime of experiment')
    # plt.savefig('avg_runtime_as_func_of_lenght_100')
    # plt.show()






if __name__ == '__main__':
    main()