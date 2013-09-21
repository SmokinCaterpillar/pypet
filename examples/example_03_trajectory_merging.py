__author__ = 'robert'


from pypet.environment import Environment
from pypet.utils.explore import cartesian_product


# Let's reuse the simple multiplication example
def multiply(traj):
    z=traj.x*traj.y
    traj.f_add_result('z',z=z, comment='Im the product of two reals!')



# Create 2 environments that handles running
env1 = Environment(trajectory='Traj1',filename='experiments/example_03/HDF5/example_03.hdf5',
                  file_title='Example_03', log_folder='experiments/example_03/LOGS/')

env2 = Environment(trajectory='Traj2',filename='experiments/example_03/HDF5/example_03.hdf5',
                  file_title='Example_03', log_folder='experiments/example_03/LOGS/')

# Get the trajectories from the environment
traj1 = env1.v_trajectory
traj2 = env2.v_trajectory

# Add both parameters
traj1.f_add_parameter('x', 1.0, comment='Im the first dimension!')
traj1.f_add_parameter('y', 1.0, comment='Im the second dimension!')
traj2.f_add_parameter('x', 1.0, comment='Im the first dimension!')
traj2.f_add_parameter('y', 1.0, comment='Im the second dimension!')

# Explore the parameters with a cartesian product for the first trajectory:
traj1.f_explore(cartesian_product({'x':[1.0,2.0,3.0,4.0], 'y':[6.0,7.0,8.0]}))
# Let's explore slightly differently for the second:
traj2.f_explore(cartesian_product({'x':[3.0,4.0,5.0,6.0], 'y':[7.0,8.0,9.0]}))

# Run the simulation
env1.f_run(multiply)
env2.f_run(multiply)

#Now we merge them together into traj1
#We want to remove duplicate entries
# like the x=3.0, y=7.0, which have been explored by both trajectories
# therefore remove_duplicates=True (Note this takes O(N1*N2)!!
# We also want to backup both trajectories, but we let the system choose the filename
# therefore backup_filename=True and not a string
# We want to move the hdf5 nodes from one trajectory to the other
# therefore move_nodes=True
# We want to delete the other trajectory afterwards, since we have already a backup
traj1.f_merge(traj2,remove_duplicates=True,backup_filename=True,
              move_nodes=True,delete_trajectory=True)

#And that's it, now we can take a look at the new trajectory and print all x,y,z triplets
#First load update data
traj1.f_load(load_parameters=-2,load_results=-2)
for run in traj1:
    x=run.x
    y=run.y
    z=run.cr.z
    # Results don't have fast access so we need to get the z value from the result z
    z = z.z
    print 'run_%d: x=%f, y=%f, z=%f' % (run.v_idx,x,y,z)

# As you can see a only the non duplicate entries are there,
# If you wish you can take a look at the files and backup files in
# the experiments/example_03/HDF5 directory