__author__ = 'robert'



from pypet import Environment, Trajectory,progressbar
from pypet.tests.testutils.ioutils import make_temp_dir, get_log_config
import os
import time
import matplotlib.pyplot as plt

def job(traj):
    traj.f_ares('result', 42, comment='A result')

def test_progress():
    print('\n\n')
    total = 100
    for irun in range(total):
        time.sleep(0.1)
        progressbar(irun, total)


def main():
    filename = os.path.join('tmp', 'hdf5', 'many_runs.hdf5')
    with Environment(filename = filename,
                      log_levels=50, report_progress=(2, 'progress', 50),
                      overwrite_file=True) as env:

        traj = env.v_traj

        traj.par.x = 0, 'parameter'

        traj.f_explore({'x': range(10000)})

        env.f_run(job)

        dicts = [traj.f_get_run_information(x) for x in range(len(traj))]
        runtimes = [dic['finish_timestamp'] - dic['timestamp'] for dic in dicts]

    plt.plot(runtimes)
    plt.show()



if __name__ == '__main__':
    #test_progress()
    main()