__author__ = 'Robert Meyer'


from pypet.trajectory import Trajectory, SingleRun
from pypet.storageservice import LazyStorageService

import logging
import cProfile

def prepare():
    logging.basicConfig(level = logging.INFO)
    traj = Trajectory('Test')



    traj.v_storage_service=LazyStorageService()


    large_amount = 11111

    for irun in range(large_amount):
        name = 'Hurz.L' + str(irun)

        traj.f_add_parameter(name,irun)


    traj.f_add_parameter('Hurz.Test', data=1)

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