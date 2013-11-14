__author__ = 'Robert Meyer'


from pypet.environment import Environment
from pypet.utils.explore import cartesian_product


def multiply(traj):
    """Sophisticated numerical simulation that involves multiplying two real values.

    :param traj:

        The trajectory containing a particular parameter combination.
        It also serves as a container for the results.

    """
    z=traj.x*traj.y
    traj.f_add_result('z',z, comment='Result of our simulation!')



# Create an environment that handles running
env = Environment(trajectory='Example1_Quick_And_Not_So_Dirty',filename='experiments/example_01/HDF5/example_01.hdf5',
                  file_title='Example1_Quick_And_Not_So_Dirty', log_folder='experiments/example_01/LOGS/',
                  comment='The first example!')

# The environment has created a trajectory container for us
traj = env.v_trajectory

# Add both parameters
traj.f_add_parameter('x', 1, comment='Im the first dimension!')
traj.f_add_parameter('y', 1, comment='Im the second dimension!')

# Explore the parameters with a cartesian product:
traj.f_explore(cartesian_product({'x':[1,2,3,4], 'y':[6,7,8]}))

# Run the simulation
env.f_run(multiply)
