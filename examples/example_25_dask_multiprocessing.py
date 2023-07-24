""" Example how to use dask (http://dask.com/) with pypet.

Start the script via ``TODO``.

"""

__author__ = 'Lars Kaiser'

import os

from pypet import Environment, cartesian_product
from pypet import pypetconstants

from dask.distributed import Client, LocalCluster

# Let's reuse the simple multiplication example
def multiply(traj):
    """Sophisticated simulation of multiplication"""
    z=traj.x*traj.y
    traj.f_add_result('z',z=z, comment='I am the product of two reals!')


def main(client: Client):
    """Main function to protect the *entry point* of the program.
    """
    # Create an environment that handles running.
    # Let's enable multiprocessing with dask:
    filename = os.path.join('hdf5', 'example_25.hdf5')
    env = Environment(trajectory='Example_25_DASK',
                      filename=filename,
                      file_title='Example_25_DASK',
                      log_stdout=True,
                      comment='Multiprocessing example using DASK!',
                      multiproc=True,
                      #freeze_input=True, # We want to save overhead and freeze input
                      use_dask=True, # Yes we want DASK!
                      dask_client=client,
                      wrap_mode=pypetconstants.WRAP_MODE_LOCAL,
                      overwrite_file=True)

    # Get the trajectory from the environment
    traj = env.trajectory

    # Add both parameters
    traj.f_add_parameter('x', 1.0, comment='I am the first dimension!')
    traj.f_add_parameter('y', 1.0, comment='I am the second dimension!')

    # Explore the parameters with a cartesian product, but we want to explore a bit more
    traj.f_explore(cartesian_product({'x':[float(x) for x in range(20)],
                                      'y':[float(y) for y in range(20)]}))
    # Run the simulation
    env.run(multiply)

    # Let's check that all runs are completed!
    assert traj.f_is_completed()

    # Finally disable logging and close all log-files
    env.disable_logging()


if __name__ == '__main__':
    # This will execute the main function in case the script is called from the one true
    # main process and not from a child processes spawned by your environment.
    # Necessary for multiprocessing under Windows.
    cluster = LocalCluster()
    client = Client(cluster)
    main(client=client)