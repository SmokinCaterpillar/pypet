__author__ = 'Robert Meyer'

import os # For path names being viable under Windows and Linux

from pypet import Environment, cartesian_product
from pypet import pypetconstants


def multiply(traj):
    """Sophisticated simulation of multiplication"""
    z=traj.x*traj.y
    traj.f_add_result('z',z, comment='I am the product of two reals!')



# Create an environment that handles running
filename = os.path.join('hdf5', 'example_08.hdf5')
env = Environment(trajectory='Example08',filename=filename,
                  file_title='Example08',
                  overwrite_file=True,
                  comment='Another example!')

# Get the trajectory from the environment
traj = env.trajectory

# Add both parameters
traj.f_add_parameter('x', 1, comment='I am the first dimension!')
traj.f_add_parameter('y', 1, comment='I am the second dimension!')

# Explore the parameters with a cartesian product:
traj.f_explore(cartesian_product({'x':[1,2,3,4], 'y':[6,7,8]}))

# Run the simulation
env.run(multiply)

# We load all results
traj.f_load(load_results=pypetconstants.LOAD_DATA)

# And now we want to find som particular results, the ones where x was 2 or y was 8.
# Therefore, we use a lambda function
my_filter_predicate= lambda x,y: x==2 or y==8

# We can now use this lambda function to search for the run indexes associated with x==2 OR y==8.
# We need a list specifying the names of the parameters and the predicate to do this.
# Note that names need to be in the order as listed in the lambda function, here 'x' and 'y':
idx_iterator = traj.f_find_idx(['x','y'], my_filter_predicate)

# Now we can print the corresponding results:
print('The run names and results for parameter combinations with x==2 or y==8:')
for idx in idx_iterator:
    # We focus on one particular run. This is equivalent to calling `traj.f_set_crun(idx)`.
    traj.v_idx=idx
    run_name = traj.v_crun
    # and print everything nicely
    print('%s: x=%d, y=%d, z=%d' %(run_name, traj.x, traj.y, traj.crun.z))

# And we do not forget to set everything back to normal
traj.f_restore_default()

# Finally disable logging and close all log-files
env.disable_logging()