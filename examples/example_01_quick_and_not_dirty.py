__author__ = 'Robert Meyer'


from pypet.environment import Environment
from pypet.utils.explore import cartesian_product


def multiply(traj):
    z=traj.x*traj.y
    traj.f_add_result('z',z, comment='Im the product of two reals!')



# Create an environment that handles running
env = Environment(trajectory='Example1_Quick_And_Not_So_Dirty',filename='experiments/example_01/HDF5/example_01.hdf5',
                  file_title='Example1_Quick_And_Not_So_Dirty', log_folder='experiments/example_01/LOGS/',
                  comment='The first example!')

# Get the trajectory from the environment
traj = env.v_trajectory

# Add both parameters
traj.f_add_parameter('x', 1.0, comment='Im the first dimension!')
traj.f_add_parameter('y', 1.0, comment='Im the second dimension!')

# Explore the parameters with a cartesian product:
traj.f_explore(cartesian_product({'x':[1.0,2.0,3.0,4.0], 'y':[6.0,7.0,8.0]}))

# Run the simulation
env.f_run(multiply)
