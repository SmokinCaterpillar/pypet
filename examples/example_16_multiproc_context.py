__author__ = 'Robert Meyer'

import os
import multiprocessing as mp
import logging

from pypet import Trajectory, MultiprocContext


def manipulate_multiproc_safe(traj):
    """ Target function that manipulates the trajectory.

    Stores the current name of the process into the trajectory and
    **overwrites** previous settings.

    :param traj:

        Trajectory container with multiprocessing safe storage service

    """

    # Manipulate the data in the trajectory
    traj.last_process_name = mp.current_process().name
    # Store the manipulated data
    traj.results.f_store(store_data=3)  # Overwrites data on disk
    # Not recommended, here only for demonstration purposes :-)


def main():
    # We don't use an environment so we enable logging manually
    logging.basicConfig(level=logging.INFO)

    filename = os.path.join('hdf5','example_16.hdf5')
    traj = Trajectory(filename=filename, overwrite_file=True)

    # The result that will be manipulated
    traj.f_add_result('last_process_name', 'N/A',
                      comment='Name of the last process that manipulated the trajectory')

    with MultiprocContext(trajectory=traj, wrap_mode='LOCK') as mc:
        # The multiprocessing context manager wraps the storage service of the trajectory
        # and passes the wrapped service to the trajectory.
        # Also restores the original storage service in the end.
        # Moreover, wee need to use the `MANAGER_LOCK` wrapping because the locks
        # are pickled and send to the pool for all function executions

        # Start a pool of processes manipulating the trajectory
        iterable = (traj for x in range(50))
        pool = mp.Pool(processes=4)
        # Pass the trajectory and the function to the pool and execute it 20 times
        pool.map_async(manipulate_multiproc_safe, iterable)
        pool.close()
        # Wait for all processes to join
        pool.join()

    # Reload the data from disk and overwrite the existing result in RAM
    traj.results.f_load(load_data=3)
    # Print the name of the last process the trajectory was manipulated by
    print('The last process to manipulate the trajectory was: `%s`' % traj.last_process_name)


if __name__ == '__main__':
    main()