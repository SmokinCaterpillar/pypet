__author__ = 'Robert Meyer'

import numpy as np
import os # For path names being viable under Windows and Linux

from pypet.trajectory import Trajectory
from pypet import pypetconstants

# Here I show how to store and load results in parts if they are quite large.
# I will skip using an environment and only work with a trajectory.

# We can create a trajectory and hand it a filename directly and it will create an
# HDF5StorageService for us:
filename = os.path.join('hdf5', 'example_09.hdf5')
traj = Trajectory(name='example_09_huge_data',
                  filename=filename,
                  overwrite_file=True)

# Now we directly add a huge result. Note that we could do the exact same procedure during
# a single run, there is no syntactical difference.
# However, the sub branch now is different, the result will be found under `traj.results.trajectory`
# instead of `traj.results.run_XXXXXXXX` (where XXXXXXX is the current run index, e.g. 00000007).
# We will add two large matrices a 100 by 100 by 100 one and 1000 by 1000 one, both containing
# random numbers. They are called `mat1` and `mat2` and are handled by the same result object
# called `huge_matrices`:
traj.f_add_result('huge_matrices',
                  mat1 = np.random.rand(100,100,100),
                  mat2 = np.random.rand(1000,1000))

# Note that the result will not support fast access since it contains more than a single
# data item. Even if there was only `mat1`, because the name is `mat1` instead of `huge_matrices`
# (as the result object itself is called), fast access does not work either.
# Yet, we can access data via natural naming using the names `mat1` and `mat2` e.g.:
val_mat1 = traj.huge_matrices.mat1[10,10,10]
val_mat2 = traj.huge_matrices.mat2[42,13]
print('mat1 contains %f at position [10,10,10]' % val_mat1)
print('mat2 contains %f at position [42,13]' % val_mat2)

# Ok that was enough analysis of the data and should be sufficient for a phd thesis (in economics).
# Let's store our trajectory and subsequently free the space for something completely different.
traj.f_store()

# We free the data:
traj.huge_matrices.f_empty()

# Check if the data was deleted
if traj.huge_matrices.f_is_empty():
    print('As promised: Nothing there!')
else:
    print('What a disappointing peace of crap this software is!')

# Lucky, it worked.
# Ok we could it add some more stuff to the result object if we want to:
traj.huge_matrices.f_set(monty='Always look on the bright side of life!')

# Next we can store our new string called monty to disk. Since our trajectory was already
# stored to disk once, we can make use of the functionality to store individual items:
traj.f_store_item('huge_matrices')

# Neat, hu? Ok now let's load some of it back, for educational purposes let's start with a fresh
# trajectory. Let's keep the old trajectory name in mind. The current time is added to the
# trajectory name on creation (if you do not want this, just say `add_time=False`).
# Thus, the name is not `example_09_huge_data`, but `example_09_huge_data_XXXX_XX_XX_XXhXXmXXs`:
old_traj_name = traj.v_name
del traj
traj = Trajectory(filename=filename)

# We only want to load the skeleton but not the data:
traj.f_load(name=old_traj_name, load_results=pypetconstants.LOAD_SKELETON)

# Check if we only loaded the skeleton, that means the `huge_matrices` result must be empty:
if traj.huge_matrices.f_is_empty():
    print('Told you!')
else:
    print('Unbelievable, this sucks!')

# Now let's only load `monty` and `mat1`.
# We can do this by passing the keyword argument `load_only` to the load item function:
traj.f_load_item('huge_matrices', load_only=['monty','mat1'])

# Check if this worked:
if ('monty' in traj.huge_matrices and
     'mat1' in traj.huge_matrices and
      not 'mat2' in traj.huge_matrices ):

    val_mat1 = traj.huge_matrices.mat1[10,10,10]
    print('mat1 contains %f at position [10,10,10]' % val_mat1)
    print('And do not forget: %s' % traj.huge_matrices.monty)
else:
    print('That\'s it, I quit! I cannot work like this!')

# Thanks for your attention!