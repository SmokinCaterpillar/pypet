__author__ = 'robert'


from pypet.environment import Environment
from pypet.utils.explore import cartesian_product
from pypet import pypetconstants


# Let's reuse the simple multiplication example
def multiply(traj):
    z=traj.x*traj.y
    traj.f_add_result('z',z=z, comment='Im the product of two reals!')



# Create an environment that handles running
#Let's enable multiprocessing with A queue and 2 workers
env = Environment(trajectory='Example_04_MP',
                  filename='experiments/example_04/HDF5/example_04.hdf5',
                  file_title='Example_04_MP',
                  log_folder='experiments/example_04/LOGS/',
                  comment = 'Multiprocessing example!',
                  multiproc=True,
                  ncores=2,
                  wrap_mode=pypetconstants.WRAP_MODE_QUEUE)

# Get the trajectory from the environment
traj = env.v_trajectory

# Add both parameters
traj.f_add_parameter('x', 1.0, comment='Im the first dimension!')
traj.f_add_parameter('y', 1.0, comment='Im the second dimension!')

# Explore the parameters with a cartesian product, but we want to think big this time:
traj.f_explore(cartesian_product({'x':[float(x) for x in range(10)], 'y':[float(y) for y in range(10)]}))

#Let's switch off the large overview tables to decrease the file size
env.f_switch_off_large_overview()


# Run the simulation
env.f_run(multiply)