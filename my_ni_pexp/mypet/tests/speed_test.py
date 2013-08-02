__author__ = 'robert'

import numpy as np
from mypet.parameter import Parameter
from mypet.trajectory import Trajectory, SingleRun
from mypet.storageservice import LazyStorageService
from mypet.utils.explore import identity
import pickle
import logging
import cProfile

def prepare():
    logging.basicConfig(level = logging.INFO)
    traj = Trajectory('Test')



    traj.set_storage_service(LazyStorageService())


    large_amount = 1111

    for irun in range(large_amount):
        name = 'Hurz.L' + str(irun)

        traj.ap(name,value = irun)


    traj.ap('Hurz.Test', value=1)

    return traj


def print_val():
    print traj.get(what)

def main():
    global traj
    global what
    traj=prepare()


    what = 'Par.Hurz.Test'

    cProfile.run('print_val()',sort=1)

if __name__ == '__main__':
    main()