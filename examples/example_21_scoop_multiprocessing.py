""" Example how to use SCOOP (http://scoop.readthedocs.org/en/0.7/) with pypet.

Start the script via ``python -m scoop example_21_scoop_multiprocessing.py``.

"""

__author__ = 'Robert Meyer'

import os # For path names being viable under Windows and Linux

from pypet import Environment, cartesian_product
from pypet import pypetconstants


# Let's reuse the simple multiplication example
def multiply(traj):
    """Sophisticated simulation of multiplication"""
    z=traj.x*traj.y
    traj.f_add_result('z',z=z, comment='I am the product of two reals!')


def main():
    """Main function to protect the *entry point* of the program.

    If you want to use multiprocessing with SCOOP you need to wrap your
    main code creating an environment into a function. Otherwise
    the newly started child processes will re-execute the code and throw
    errors (also see http://scoop.readthedocs.org/en/latest/usage.html#pitfalls).

    """

    # Create an environment that handles running.
    # Let's enable multiprocessing with scoop:
    filename = os.path.join('hdf5', 'example_21.hdf5')
    env = Environment(trajectory='Example_21_SCOOP',
                      filename=filename,
                      file_title='Example_21_SCOOP',
                      log_stdout=True,
                      comment='Multiprocessing example using SCOOP!',
                      multiproc=True,
                      freeze_input=True, # We want to save overhead and freeze input
                      use_scoop=True, # Yes we want SCOOP!
                      wrap_mode=pypetconstants.WRAP_MODE_LOCAL,  # SCOOP only works with 'LOCAL'
                      # or 'NETLOCK' wrapping
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
    main()