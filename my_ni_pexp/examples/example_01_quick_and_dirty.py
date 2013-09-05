__author__ = 'Robert Meyer'


from mypet.environment import Environment
from mypet.utils.explore import cartesian_product


def multiply(traj):
    z=traj.x*traj.y
    traj.add_result('z',z=z, comment='Im the product of two reals!')


# Create and environment that handles running
env = Environment(trajectory='Example1_Quick_And_Dirty',filename='./HDF/example1_quick_and_dirty.hdf5',
                  filetitle='Quick_And_Dirty', logfolder='./LOGS/')

# Get the trajectory from the environment
traj = env.get_trajectory()

# Add both parameters
traj.add_parameter('x', 1.0, comment='Im the first dimension!')
traj.add_parameter('y', 1.0, comment='Im the second dimension!')

# Explore the parameters with a cartesian product:
traj.explore(cartesian_product,{'x':[1.0,2.0,3.0,4.0], 'y':[6.0,7.0,8.0]})

# Run the simulation
env.run(multiply)