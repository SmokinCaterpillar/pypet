__author__ = 'Robert Meyer'

import os # To allow file paths working under Windows and Linux

from pypet import Environment, Result, Parameter

def multiply(traj):
    """Example of a sophisticated simulation that involves multiplying two values.

    :param traj:

        Trajectory containing
        the parameters in a particular combination,
        it also serves as a container for results.

    """
    z=traj.mylink1*traj.mylink2 # And again we now can also use the different names
    # due to the creation of links
    traj.f_add_result('runs.$.z', z, comment='Result of our simulation!')


# Create an environment that handles running
filename = os.path.join('hdf5','example_14.hdf5')
env = Environment(trajectory='Multiplication',
                  filename=filename,
                  file_title='Example_14_Links',
                  overwrite_file=True,
                  comment='How to use links')

# The environment has created a trajectory container for us
traj = env.trajectory

# Add both parameters
traj.par.x = Parameter('x', 1, 'I am the first dimension!')
traj.par.y = Parameter('y', 1, 'I am the second dimension!')

# Explore just two points
traj.f_explore({'x': [3, 4]})

# So far everything was as in the first example. However now we add links:
traj.f_add_link('mylink1', traj.f_get('x'))
# Note the `f_get` here to ensure to get the parameter instance, not the value 1
# This allows us now to access x differently:
print('x=' + str(traj.mylink1))
# We can try to avoid fast access as well, and recover the original parameter
print(str(traj.f_get('mylink1')))
# And also colon notation is allowed that creates new groups on the fly
traj.f_add_link('parameters.mynewgroup.mylink2', traj.f_get('y'))



# And, of course, we can also use the links during run:
env.run(multiply)

# Finally disable logging and close all log-files
env.disable_logging()

