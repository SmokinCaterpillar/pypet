"""Script to plot the fano factor graph for a given simulation
stored as a trajectory to an HDF5 file.

"""

__author__ = 'Robert Meyer'

import os
import matplotlib.pyplot as plt

from pypet.trajectory import Trajectory
from pypet.brian.parameter import BrianMonitorResult, BrianParameter, BrianDurationParameter



def main():

    folder = 'experiments/example_11/HDF5/'
    filename = 'Clustered_Network_2014_01_22_10h02m01s.hdf5' # Change this to the name of your
    # hdf5 file. The very first trajectory in this file is loaded.

    filename = os.path.join(folder, filename)
    # If we pass a filename to the trajectory a new HDF5StorageService will
    # be automatically created
    traj = Trajectory(filename=filename,
                    dynamically_imported_classes=[BrianDurationParameter,
                                                  BrianMonitorResult,
                                                  BrianParameter])

    # Load the trajectory, but onyl laod the skeleton of the results
    traj.f_load(index=0, # Change if you do not want to load the very first trajectory
                load_parameters=2,
                load_derived_parameters=2,
                load_results=1)

    # Find the result instances related to the fano factor
    fano_dict = traj.f_get_from_runs('mean_fano_factor', fast_access=False)

    # Load the data of the fano factor results
    ffs = fano_dict.values()
    traj.f_load_items(ffs)

    # Extract all values and R_ee values for each run
    ffs_values = [x.f_get() for x in ffs]
    Rees = traj['R_ee'].f_get_range()

    # Plot average fano factor as a function of R_ee
    plt.plot(Rees, ffs_values)
    plt.xlabel('R_ee')
    plt.ylabel('Avg. Fano Factor')
    plt.show()


if __name__ == '__main__':
    main()