__author__ = 'robert'

import os

from pypet.trajectory import Trajectory
from pypet.brian.parameter import BrianMonitorResult, BrianParameter, BrianDurationParameter
import matplotlib.pyplot as plt


def main():

    folder = '../HDF5/'
    filename = 'Clustered_Network_2013_12_25_08h28m02s.hdf5'

    filename = os.path.join(folder, filename)


    traj = Trajectory(filename=filename,
                    dynamically_imported_classes=[BrianDurationParameter,
                                                  BrianMonitorResult,
                                                  BrianParameter])

    traj.f_load(index=0, load_parameters=2, load_derived_parameters=2, load_results=1)

    fano_dict = traj.f_get_from_runs('mean_fano_factor', fast_access=False)

    ffs = fano_dict.values()

    traj.f_load_items(ffs)

    ffs_values = [x.f_get() for x in ffs]

    Rees = traj['R_ee'].f_get_range()

    plt.plot(Rees, ffs_values)
    plt.xlabel('R_ee')
    plt.ylabel('Avg. Fano Factor')

    plt.show()


if __name__ == '__main__':
    main()