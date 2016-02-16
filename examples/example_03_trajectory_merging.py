__author__ = 'Robert Meyer'

import os # For using pathnames under Windows and Linux

from pypet import Environment, cartesian_product


# Let's reuse the simple multiplication example
def multiply(traj):
    """Sophisticated simulation of multiplication"""
    z=traj.x*traj.y
    traj.f_add_result('z',z=z, comment='I am the product of two reals!',)



# Create 2 environments that handle running
filename = os.path.join('hdf5', 'example_03.hdf5')
env1 = Environment(trajectory='Traj1',
                   filename=filename,
                   file_title='Example_03',
                   add_time=True,  # Add the time of trajectory creation to its name
                   comment='I will be increased!')

env2 = Environment(trajectory='Traj2',
                   filename=filename,
                   file_title='Example_03', log_config=None, # One environment keeping log files
                   # is enough
                   add_time=True,
                   comment = 'I am going to be merged into some other trajectory!')

# Get the trajectories from the environment
traj1 = env1.trajectory
traj2 = env2.trajectory

# Add both parameters
traj1.f_add_parameter('x', 1.0, comment='I am the first dimension!')
traj1.f_add_parameter('y', 1.0, comment='I am the second dimension!')
traj2.f_add_parameter('x', 1.0, comment='I am the first dimension!')
traj2.f_add_parameter('y', 1.0, comment='I am the second dimension!')

# Explore the parameters with a cartesian product for the first trajectory:
traj1.f_explore(cartesian_product({'x':[1.0,2.0,3.0,4.0], 'y':[6.0,7.0,8.0]}))
# Let's explore slightly differently for the second:
traj2.f_explore(cartesian_product({'x':[3.0,4.0,5.0,6.0], 'y':[7.0,8.0,9.0]}))


# Run the simulations with all parameter combinations
env1.run(multiply)
env2.run(multiply)

# Now we merge them together into traj1
# We want to remove duplicate entries
# like the parameter space point x=3.0, y=7.0.
# Several points have been explored by both trajectories and we need them only once.
# Therefore, we set remove_duplicates=True (Note this takes O(N1*N2)!).
# We also want to backup both trajectories, but we let the system choose the filename.
# Accordingly we choose backup_filename=True instead of providing a filename.
# We want to move the hdf5 nodes from one trajectory to the other.
# Thus we set move_nodes=True.
# Finally,we want to delete the other trajectory afterwards since we already have a backup.
traj1.f_merge(traj2,
              remove_duplicates=True,
              backup_filename=True,
              move_data=True,
              delete_other_trajectory=True)

# And that's it, now we can take a look at the new trajectory and print all x,y,z triplets.
# But before that we need to load the data we computed during the runs from disk.
# We choose load_parameters=2 and load_results=2 since we want to load all data and not only
# the skeleton
traj1.f_load(load_parameters=2, load_results=2)

for run_name in traj1.f_get_run_names():
    # We can make the trajectory belief it is a single run. All parameters will
    # be treated as they were in the specific run. And we can use the `crun` wildcard.
    traj1.f_set_crun(run_name)
    x=traj1.x
    y=traj1.y
    # We need to specify the current run, because there exists more than one z value
    z=traj1.crun.z
    print('%s: x=%f, y=%f, z=%f' % (run_name, x, y, z))

# Don't forget to reset you trajectory to the default settings, to release its belief to
# be the last run.
traj1.f_restore_default()

# As you can see duplicate parameter space points have been removed.
# If you wish you can take a look at the files and backup files in
# the experiments/example_03/HDF5 directory

# Finally, disable logging and close log files
env1.disable_logging()