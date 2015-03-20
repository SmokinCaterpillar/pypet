__author__ = 'robert'



from pypet import Environment, Trajectory
from pypet.tests.testutils.ioutils import make_temp_dir, get_log_config
import os
import matplotlib.pyplot as plt
import numpy as np
import time

SIZE = 100

def job(traj):
    traj.f_ares('set_%d.$.result' % int(traj.v_idx / SIZE), 42, comment='A result')



def get_runtime(length):
    filename = os.path.join('tmp', 'hdf5', 'many_runs_improved.hdf5')
    start = time.time()
    with Environment(filename = filename,
                      log_levels=50, report_progress=(2, 'progress', 50),
                      overwrite_file=True, purge_duplicate_comments=False,
                      summary_tables=False, small_overview_tables=False) as env:

        traj = env.v_traj

        traj.par.x = 0, 'parameter'

        traj.f_explore({'x': range(length)})

        max_run = 1000000000

        for idx in range(len(traj)):
            if idx > max_run:
                traj.f_get_run_information(idx, copy=False)['completed'] = 1

        env.f_run(job)
        end = time.time()
        dicts = [traj.f_get_run_information(x) for x in range(min(len(traj), max_run))]
    total = end - start
    return total/float(len(traj)), total

def main():
    lengths = [5000, 1000, 500, 100, 50, 10, 5, 1]
    runtimes = [get_runtime(x) for x in lengths]
    avg_runtimes = [x[0] for x in runtimes]
    summed_runtime = [x[1] for x in runtimes]

    plt.subplot(2, 1, 1)
    plt.semilogx(lengths, avg_runtimes, linewidth=2)
    plt.xlabel('Runs')
    plt.ylabel('t[s]')
    plt.title('Average Runtime per single run')
    plt.grid()
    plt.subplot(2, 1, 2)
    plt.loglog(lengths, summed_runtime, linewidth=2)
    plt.grid()
    plt.xlabel('Runs')
    plt.ylabel('t[s]')
    plt.title('Total runtime of experiment')
    plt.show()





if __name__ == '__main__':
    main()