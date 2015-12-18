__author__ = 'Robert Meyer'

import os # For path names being viable under Windows and Linux
import logging

from pypet import Environment, cartesian_product
from pypet import pypetconstants


# Let's reuse the simple multiplication example
def multiply(traj):
    """Sophisticated simulation of multiplication"""
    z=traj.x*traj.y
    traj.f_add_result('z',z=z, comment='I am the product of two reals!')


def main():
    """Main function to protect the *entry point* of the program.

    If you want to use multiprocessing under Windows you need to wrap your
    main code creating an environment into a function. Otherwise
    the newly started child processes will re-execute the code and throw
    errors (also see https://docs.python.org/2/library/multiprocessing.html#windows).

    """

    # Create an environment that handles running.
    # Let's enable multiprocessing with 2 workers.
    filename = os.path.join('hdf5', 'example_04.hdf5')
    env = Environment(trajectory='Example_04_MP',
                      filename=filename,
                      file_title='Example_04_MP',
                      log_stdout=True,
                      comment='Multiprocessing example!',
                      multiproc=True,
                      ncores=4,
                      use_pool=True,  # Our runs are inexpensive we can get rid of overhead
                      # by using a pool
                      freeze_input=True,  # We can avoid some
                      # overhead by freezing the input to the pool
                      wrap_mode=pypetconstants.WRAP_MODE_QUEUE,
                      graceful_exit=True,  # We want to exit in a data friendly way
                      # that safes all results after hitting CTRL+C, try it ;-)
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

    # Finally disable logging and close all log-files
    env.disable_logging()


if __name__ == '__main__':
    # This will execute the main function in case the script is called from the one true
    # main process and not from a child processes spawned by your environment.
    # Necessary for multiprocessing under Windows.
    main()