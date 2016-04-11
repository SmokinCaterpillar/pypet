"""Script to plot the fano factor graph for a given simulation
stored as a trajectory to an HDF5 file.

"""

__author__ = 'Robert Meyer'

import os
import matplotlib.pyplot as plt

from pypet import Trajectory, Environment
from pypet.brian2.parameter import Brian2MonitorResult, Brian2Parameter


def main():

    filename = os.path.join('hdf5', 'Clustered_Network.hdf5')
    # If we pass a filename to the trajectory a new HDF5StorageService will
    # be automatically created
    traj = Trajectory(filename=filename,
                    dynamically_imported_classes=[Brian2MonitorResult,
                                                  Brian2Parameter])

    # Let's create and fake environment to enable logging:
    env = Environment(traj, do_single_runs=False)


    # Load the trajectory, but onyl laod the skeleton of the results
    traj.f_load(index=-1, load_parameters=2, load_derived_parameters=2, load_results=1)

    # Find the result instances related to the fano factor
    fano_dict = traj.f_get_from_runs('mean_fano_factor', fast_access=False)

    # Load the data of the fano factor results
    ffs = fano_dict.values()
    traj.f_load_items(ffs)

    # Extract all values and R_ee values for each run
    ffs_values = [x.f_get() for x in ffs]
    Rees = traj.f_get('R_ee').f_get_range()

    # Plot average fano factor as a function of R_ee
    plt.plot(Rees, ffs_values)
    plt.xlabel('R_ee')
    plt.ylabel('Avg. Fano Factor')
    plt.show()

    # Finally disable logging and close all log-files
    env.disable_logging()


if __name__ == '__main__':
    main()