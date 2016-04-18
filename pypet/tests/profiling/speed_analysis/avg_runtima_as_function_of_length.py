__author__ = 'robert'



from pypet import Environment, Trajectory
from pypet.tests.testutils.ioutils import make_temp_dir, get_log_config
import os
import matplotlib.pyplot as plt
import numpy as np
import time

def job(traj):
    traj.f_ares('$set.$', 42, comment='A result')



def get_runtime(length):
    filename = os.path.join('tmp', 'hdf5', 'many_runs.hdf5')

    with Environment(filename = filename,
                      log_levels=50, report_progress=(0.0002, 'progress', 50),
                      overwrite_file=True, purge_duplicate_comments=False,
                      log_stdout=False,
                      multiproc=False, ncores=2, use_pool=True,
                      wrap_mode='PIPE', #freeze_input=True,
                      summary_tables=False, small_overview_tables=False) as env:

        traj = env.v_traj

        traj.par.f_apar('x', 0, 'parameter')

        traj.f_explore({'x': range(length)})

        # traj.v_full_copy = False

        max_run = 1000

        for idx in range(len(traj)):
            if idx > max_run:
                traj.f_get_run_information(idx, copy=False)['completed'] = 1
        start = time.time()
        env.f_run(job)
        end = time.time()
        # dicts = [traj.f_get_run_information(x) for x in range(min(len(traj), max_run))]
    total = end - start
    return total/float(min(len(traj), max_run)), total/float(min(len(traj), max_run)) * len(traj)

def main():
    #lengths = [1000000, 500000, 100000, 50000, 10000, 5000, 1000, 500, 100, 50, 10, 5, 1]
    lengths = [100000, 50000, 10000, 5000, 1000, 500, 100, 50, 10, 5, 1]
    runtimes = [get_runtime(x) for x in lengths]
    avg_runtimes = [x[0] for x in runtimes]
    summed_runtime = [x[1] for x in runtimes]

    plt.subplot(2, 1, 1)
    plt.semilogx(list(reversed(lengths)), list(reversed(avg_runtimes)), linewidth=2)
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
    plt.savefig('avg_runtime_as_func_of_lenght_1000_single_core')
    plt.show()






if __name__ == '__main__':
    main()