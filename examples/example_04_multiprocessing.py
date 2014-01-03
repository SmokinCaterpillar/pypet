__author__ = 'Robert Meyer'


from pypet.environment import Environment
from pypet.utils.explore import cartesian_product
from pypet import pypetconstants


# Let's reuse the simple multiplication example
def multiply(traj):
    """Sophisticated simulation of multiplication"""
    z=traj.x*traj.y
    traj.f_add_result('z',z=z, comment='I am the product of two reals!')



# Create an environment that handles running.
# Let's enable multiprocessing with A queue and 2 workers.
# Since we want to explore a rather large trajectory, we switch off
# the large overview tables.
env = Environment(trajectory='Example_04_MP',
                  filename='experiments/example_04/HDF5/example_04.hdf5',
                  file_title='Example_04_MP',
                  log_folder='experiments/example_04/LOGS/',
                  comment = 'Multiprocessing example!',
                  multiproc=True,
                  ncores=2,
                  use_pool=True,
                  wrap_mode=pypetconstants.WRAP_MODE_QUEUE,
                  large_overview_tables=False)

# Get the trajectory from the environment
traj = env.v_trajectory

# Add both parameters
traj.f_add_parameter('x', 1.0, comment='I am the first dimension!')
traj.f_add_parameter('y', 1.0, comment='I am the second dimension!')

# Explore the parameters with a cartesian product, but we want to explore a bit more
traj.f_explore(cartesian_product({'x':[float(x) for x in range(15)],
                                  'y':[float(y) for y in range(15)]}))

# Run the simulation
env.f_run(multiply)