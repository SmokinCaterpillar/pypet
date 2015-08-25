__author__ = 'Robert Meyer'

import numpy as np
import os # For path names being viable under Windows and Linux

# Let's reuse the stuff from the previous example
from example_05_custom_parameter import euler_scheme, FunctionParameter, diff_lorenz

from pypet import Environment, ArrayParameter
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# Now we will add some control flow to allow to switch between the differential equations
def add_parameters(traj):
    """Adds all necessary parameters to the `traj` container.

    You can choose between two parameter sets. One for the Lorenz attractor and
    one for the Roessler attractor.
    The former is chosen for `traj.diff_name=='diff_lorenz'`, the latter for
    `traj.diff_name=='diff_roessler'`.
    You can use parameter presetting to switch between the two cases.

    :raises: A ValueError if `traj.diff_name` is none of the above

    """
    traj.f_add_parameter('steps', 10000, comment='Number of time steps to simulate')
    traj.f_add_parameter('dt', 0.01, comment='Step size')

    # Here we want to add the initial conditions as an array parameter, since we will simulate
    # a 3-D differential equation, that is the Roessler attractor
    # (https://en.wikipedia.org/wiki/R%C3%B6ssler_attractor)
    traj.f_add_parameter(ArrayParameter,'initial_conditions', np.array([0.0,0.0,0.0]),
                         comment = 'Our initial conditions, as default we will start from'
                                   ' origin!')

    # Per default we choose the name `'diff_lorenz'` as in the last example
    traj.f_add_parameter('diff_name','diff_lorenz', comment= 'Name of our differential equation')

    # We want some control flow depending on which name we really choose
    if traj.diff_name == 'diff_lorenz':
        # These parameters are for the Lorenz differential equation
        traj.f_add_parameter('func_params.sigma', 10.0)
        traj.f_add_parameter('func_params.beta', 8.0/3.0)
        traj.f_add_parameter('func_params.rho', 28.0)
    elif traj.diff_name == 'diff_roessler':
        # If we use the Roessler system we need different parameters
        traj.f_add_parameter('func_params.a', 0.1)
        traj.f_add_parameter('func_params.c', 14.0)
    else:
        raise ValueError('I don\'t know what %s is.' % traj.diff_name)



# We need to define the Roessler function, we will assume that the value array is 3 dimensional,
# First dimension is x-component, second y-component, and third the z-component
def diff_roessler(value_array, a, c):
    """The Roessler attractor differential equation

    :param value_array: 3d array containing the x,y, and z component values.
    :param a: Constant attractor parameter
    :param c: Constant attractor parameter

    :return: 3d array of the Roessler system evaluated at `value_array`

    """
    b=a
    diff_array = np.zeros(3)
    diff_array[0] = -value_array[1] - value_array[2]
    diff_array[1] = value_array[0] + a * value_array[1]
    diff_array[2] = b + value_array[2] * (value_array[0] - c)

    return diff_array


# And here goes our main function
def main():

    filename = os.path.join('hdf5', 'example_06.hdf5')
    env = Environment(trajectory='Example_06_Euler_Integration',
                      filename=filename,
                      file_title='Example_06_Euler_Integration',
                      overwrite_file=True,
                      comment = 'Go for Euler!')


    traj = env.trajectory

    # 1st a) phase parameter addition
    # Remember we have some control flow in the `add_parameters` function, the default parameter
    # set we choose is the `'diff_lorenz'` one, but we want to deviate from that and use the
    # `'diff_roessler'`.
    # In order to do that we can preset the corresponding name parameter to change the
    # control flow:
    traj.f_preset_parameter('diff_name', 'diff_roessler') # If you erase this line, you will get
                                                          # again the lorenz attractor
    add_parameters(traj)

    # 1st b) phase preparation
    # Let's check which function we want to use
    if traj.diff_name=='diff_lorenz':
        diff_eq = diff_lorenz
    elif traj.diff_name=='diff_roessler':
        diff_eq = diff_roessler
    else:
        raise ValueError('I don\'t know what %s is.' % traj.diff_name)
    # And add the source code of the function as a derived parameter.
    traj.f_add_derived_parameter(FunctionParameter, 'diff_eq', diff_eq,
                                     comment='Source code of our equation!')

    # We want to explore some initial conditions
    traj.f_explore({'initial_conditions' : [
        np.array([0.01,0.01,0.01]),
        np.array([2.02,0.02,0.02]),
        np.array([42.0,4.2,0.42])
    ]})
    # 3 different conditions are enough for now

    # 2nd phase let's run the experiment
    # We pass 'euler_scheme' as our top-level simulation function and
    # the Roessler function as an additional argument
    env.run(euler_scheme, diff_eq)

    # Again no post-processing

    # 4th phase analysis.
    # I would recommend to do the analysis completely independent from the simulation
    # but for simplicity let's do it here.
    # We won't reload the trajectory this time but simply update the skeleton
    traj.f_load_skeleton()

    #For the fun of it, let's print the source code
    print('\n ---------- The source code of your function ---------- \n %s' % traj.diff_eq)

    # Let's get the exploration array:
    initial_conditions_exploration_array = traj.f_get('initial_conditions').f_get_range()
    # Now let's plot our simulated equations for the different initial conditions.
    # We will iterate through the run names
    for idx, run_name in enumerate(traj.f_get_run_names()):

        # Get the result of run idx from the trajectory
        euler_result = traj.results.f_get(run_name).euler_evolution
        # Now we manually need to load the result. Actually the results are not so large and we
        # could load them all at once, but for demonstration we do as if they were huge:
        traj.f_load_item(euler_result)
        euler_data = euler_result.data

        # Plot fancy 3d plot
        fig = plt.figure(idx)
        ax = fig.gca(projection='3d')
        x = euler_data[:,0]
        y = euler_data[:,1]
        z = euler_data[:,2]
        ax.plot(x, y, z, label='Initial Conditions: %s' % str(initial_conditions_exploration_array[idx]))
        plt.legend()
        plt.show()

        # Now we free the data again (because we assume its huuuuuuge):
        del euler_data
        euler_result.f_empty()

    # Finally disable logging and close all log-files
    env.disable_logging()


if __name__ == '__main__':
    main()
