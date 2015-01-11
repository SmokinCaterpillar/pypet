__author__ = 'Robert Meyer'

import multiprocessing as mp
import numpy as np

from pypet import Environment, cartesian_product


def multiply(traj, result_list):
    """Example of a sophisticated simulation that involves multiplying two values.

    This time we will store tha value in a shared list and only in the end add the result.

    :param traj:

        Trajectory - or more precisely a SingleRun - containing
        the parameters in a particular combination,
        it also serves as a container for results.


    """
    z=traj.x*traj.y
    result_list[traj.v_idx] = z


def main():
    # Create an environment that handles running
    env = Environment(trajectory='Multiplication',
                      filename='experiments/example_01/HDF5/example_01.hdf5',
                      file_title='Example_01_First_Steps',
                      log_folder='experiments/example_01/LOGS/',
                      comment='The first example!',
                      continuable=False, # We have shared data in terms of a multiprocessing list,
                      # so we CANNOT use the continue feature.
                      multiproc=True,
                      ncores=2)

    # The environment has created a trajectory container for us
    traj = env.v_trajectory

    # Add both parameters
    traj.f_add_parameter('x', 1, comment='I am the first dimension!')
    traj.f_add_parameter('y', 1, comment='I am the second dimension!')

    # Explore the parameters with a cartesian product
    traj.f_explore(cartesian_product({'x':[1,2,3,4], 'y':[6,7,8]}))

    # We want a shared list where we can put all out results in. We use a manager for this:
    result_list = mp.Manager().list()
    # Let's make some space for potential results
    result_list[:] =[0 for _dummy in range(len(traj))]

    # Run the simulation
    env.f_run(multiply, result_list)

    # Now we want to store the final list as numpy array
    traj.f_add_result('z', np.array(result_list))

    # Finally let's print the result to see that it worked
    print(traj.z)

if __name__ == '__main__':
    main()