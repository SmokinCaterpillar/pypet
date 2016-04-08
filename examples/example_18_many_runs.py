"""Exploring more than 20000 runs may slow down *pypet*.

HDF5 has problems handling nodes with more than 10000 children.
To overcome this problem, simply group your runs into buckets or sets
using the `$set` wildcard.

"""

__author__ = 'Robert Meyer'


import os # To allow file paths working under Windows and Linux

from pypet import Environment
from pypet.utils.explore import cartesian_product

def multiply(traj):
    """Example of a sophisticated simulation that involves multiplying two values."""
    z = traj.x * traj.y
    # Since we perform many runs we will group results into sets of 1000 each
    # using the `$set` wildcard
    traj.f_add_result('$set.$.z', z, comment='Result of our simulation '
                                             'sorted into buckets of '
                                             '1000 runs each!')

def main():
    # Create an environment that handles running
    filename = os.path.join('hdf5','example_18.hdf5')
    env = Environment(trajectory='Multiplication',
                      filename=filename,
                      file_title='Example_18_Many_Runs',
                      overwrite_file=True,
                      comment='Contains many runs',
                      multiproc=True,
                      use_pool=True,
                      freeze_input=True,
                      ncores=2,
                      wrap_mode='QUEUE')

    # The environment has created a trajectory container for us
    traj = env.trajectory

    # Add both parameters
    traj.f_add_parameter('x', 1, comment='I am the first dimension!')
    traj.f_add_parameter('y', 1, comment='I am the second dimension!')

    # Explore the parameters with a cartesian product, yielding 2500 runs
    traj.f_explore(cartesian_product({'x': range(50), 'y': range(50)}))

    # Run the simulation
    env.run(multiply)

    # Disable logging
    env.disable_logging()

    # turn auto loading on, since results have not been loaded, yet
    traj.v_auto_load = True
    # Use the `v_idx` functionality
    traj.v_idx = 2042
    print('The result of run %d is: ' % traj.v_idx)
    # Now we can rely on the wildcards
    print(traj.res.crunset.crun.z)
    traj.v_idx = -1
    # Or we can use the shortcuts `rts_X` (run to set) and `r_X` to get particular results
    print('The result of run %d is: ' % 2044)
    print(traj.res.rts_2044.r_2044.z)

if __name__ == '__main__':
    main()