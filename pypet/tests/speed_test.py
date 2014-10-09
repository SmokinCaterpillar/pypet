__author__ = 'Robert Meyer'


from pypet.trajectory import Trajectory, SingleRun
from pypet.storageservice import LazyStorageService
from pypet.environment import Environment
from pypet.tests.test_helpers import TEMPDIR

import logging
import cProfile
import tempfile
import os
import numpy as np
import time
import shutil

from pycallgraph import PyCallGraph
from pycallgraph.output import GraphvizOutput



def add_data(traj):
    for irun in range(traj.par.res_per_run):
        traj.f_add_result('test.test.$.res_%d' % irun, 42+irun)


def run_experiments():
    logging.basicConfig(level = logging.INFO)

    logfolder = os.path.join(tempfile.gettempdir(), TEMPDIR, 'logs')
    pathfolder = os.path.join(tempfile.gettempdir(), TEMPDIR, 'hdf5')


    exponents = np.arange(0, 8, 1)
    res_per_run = 100
    traj_names = []
    filenames = []
    runs = (np.ones(len(exponents))*2) ** exponents
    for adx, nruns in enumerate(runs):
        env = Environment(log_folder=logfolder, filename=pathfolder,
                          ncores=2, multiproc=True,
                          use_pool=True,
                          wrap_mode='QUEUE')

        traj = env.v_trajectory

        traj.f_add_parameter('res_per_run', res_per_run)
        traj.f_add_parameter('trial', 0)

        traj.f_explore({'trial': list(range(int(nruns)))})


        env.f_run(add_data)

        traj_names.append(traj.v_name)
        filenames.append(traj.v_storage_service.filename)

    return filenames, traj_names, pathfolder

def test_loading(filenames, traj_names):

    loading_times = np.zeros(len(traj_names))
    loading_times_wd = np.zeros(len(traj_names))

    n_groups= np.zeros(len(traj_names), dtype='int')

    for idx, traj_name in enumerate(traj_names):
        filename = filenames[idx]
        traj = Trajectory(name=traj_name, filename=filename, add_time=False)
        start = time.time()
        traj.f_load(load_parameters=2, load_results=1, load_derived_parameters=1)
        elapsed = (time.time() - start)
        loading_times[idx]=elapsed

        n_groups[idx] = len([x for x in traj.f_iter_nodes(recursive=True)])
        del traj

        traj = Trajectory(name=traj_name, filename=filename, add_time=False)
        start = time.time()
        traj.f_load(load_all=2)
        elapsed = (time.time() - start)
        loading_times_wd[idx]=elapsed

    for idx, loading_time in enumerate(loading_times):
        loading_time_wd = loading_times_wd[idx]
        groups = n_groups[idx]
        print('Groups: %d, Loading: %.3fs, with Data: %.3fs' % (groups, loading_time, loading_time_wd))



def profile_single_storing(profile_stroing=False, profile_loading=True):

    logging.basicConfig(level = logging.INFO)

    logfolder = os.path.join(tempfile.gettempdir(), TEMPDIR, 'logs')
    pathfolder = os.path.join(tempfile.gettempdir(), TEMPDIR, 'hdf5')

    res_per_run = 100

    env = Environment(log_folder=logfolder, filename=pathfolder,
                      ncores=2, multiproc=False,
                      use_pool=True,
                      wrap_mode='QUEUE')

    traj = env.v_trajectory

    traj.f_add_parameter('res_per_run', res_per_run)
    traj.f_add_parameter('trial', 0)

    traj.f_explore({'trial':list(range(10))})

    runexp = lambda : env.f_run(add_data)


    if profile_stroing:
        cProfile.runctx('runexp()', {'runexp': runexp},globals(), sort=1,
                        filename='store_stats.profile')
    else:
        runexp()

    print('########################################################################')

    traj = Trajectory(name=traj.v_name, add_time=False, filename= traj.v_storage_service.filename)

    load = lambda : traj.f_load(load_parameters=2, load_results=1)

    if profile_loading:
        cProfile.runctx('load()', {'load': load},globals(), filename='load_stats.profile', sort=1)



def main():

    try:
        profile_single_storing(True, True)
        filenames, traj_names, path_folder = run_experiments()
        test_loading(filenames, traj_names)
    finally:
        shutil.rmtree(os.path.join(tempfile.gettempdir(), TEMPDIR),True)


if __name__ == '__main__':
    main()