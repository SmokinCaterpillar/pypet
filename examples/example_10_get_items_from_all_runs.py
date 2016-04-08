__author__ = 'Robert Meyer'

from mpl_toolkits.mplot3d import axes3d
import matplotlib.pyplot as plt
import numpy as np
import os # For path names working under Windows ans Linux

from pypet import Environment, cartesian_product
from pypet import pypetconstants


def multiply(traj):
    """Sophisticated simulation of multiplication"""
    z=traj.x * traj.y
    traj.f_add_result('z', z, comment='I am the product of two reals!')


# Create an environment that handles running
filename = os.path.join('hdf5', 'example_10.hdf5')
env = Environment(trajectory='Example10', filename=filename,
                  file_title='Example10',
                  overwrite_file=True,
                  comment='Another example!')

# Get the trajectory from the environment
traj = env.trajectory

# Add both parameters
traj.f_add_parameter('x', 1, comment='I am the first dimension!')
traj.f_add_parameter('y', 1, comment='I am the second dimension!')

# Explore the parameters with a cartesian product:
x_length = 12
y_length = 12
traj.f_explore(cartesian_product({'x': range(x_length), 'y': range(y_length)}))

# Run the simulation
env.run(multiply)

# We load all results
traj.f_load(load_results=pypetconstants.LOAD_DATA)

# We access the ranges for plotting
xs = traj.f_get('x').f_get_range()
ys = traj.f_get('y').f_get_range()

# Now we want to directly get all numbers z from all runs
# for plotting.
# We use `fast_access=True` to directly get access to
# the values.
# Moreover, since `f_get_from_runs` returns an ordered dictionary
# `values()` gives us all values already in the correct order of the runs.
zs = list(traj.f_get_from_runs(name='z', fast_access=True).values())
# We also make sure it's a list (because in python 3 ``value()`` returns an
# iterator instead of a list)

# Convert the lists to numpy 2D arrays
x_mesh = np.reshape(np.array(xs), (x_length, y_length))
y_mesh = np.reshape(np.array(ys), (x_length, y_length))
z_mesh = np.reshape(np.array(zs), (x_length, y_length))

# Make fancy 3D plot
fig=plt.figure()
ax = fig.add_subplot(111, projection='3d')
ax.plot_wireframe(x_mesh, y_mesh, z_mesh, rstride=1, cstride=1)
plt.show()

# Finally disable logging and close all log-files
env.disable_logging()
