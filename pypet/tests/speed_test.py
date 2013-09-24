__author__ = 'Robert Meyer'

import numpy as np
from pypet.parameter import Parameter
from pypet.trajectory import Trajectory, SingleRun
from pypet.storageservice import LazyStorageService
import pickle
import logging
import cProfile

def prepare():
    logging.basicConfig(level = logging.INFO)
    traj = Trajectory('Test')



    traj.set_storage_service(LazyStorageService())


    large_amount = 111111

    for irun in range(large_amount):
        name = 'Hurz.L' + str(irun)

        traj.ap(name,irun)


    traj.ap('Hurz.Test', value=1)

    return traj


def print_val():
    print traj.f_get(what)

def main():
    global traj
    global what
    traj=prepare()


    what = 'Test'

    cProfile.run('print_val()',sort=1)

if __name__ == '__main__':
    main()