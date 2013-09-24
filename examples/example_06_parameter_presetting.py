__author__ = 'robert'

import numpy as np

# Let's reuse the stuff from the previous example
from example_05_custom_parameter import euler_scheme, FunctionParameter, diff_lorenz

from pypet.environment import Environment
from pypet.parameter import ArrayParameter
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# Now we will add some control flow to add_parameters to allow to switch between 2
# differential equations
def add_parameters(traj):
    traj.f_add_parameter('steps', 10000, comment='Number of time steps to simulate')
    traj.f_add_parameter('dt', 0.01, comment='Step size')
    # Here we want to add the initial conditions as an array parameter, since we will simulate
    # a 3-D differential equation, that will be the roessler attractor
    traj.f_add_parameter(ArrayParameter,'initial_conditions', np.array([0.0,0.0,0.0]),
                         comment = 'Our initial conditions, as default we will start from'
                                   ' origin!')

    # Per default we choose the name `'diff_lorenz'`
    traj.f_add_parameter('diff_name','diff_lorenz', comment= 'Name of our differential equation')

    # We want some control flow depending on which name we choose
    if traj.diff_name == 'diff_lorenz':
        # We will group all parameters of the Lorenz differential equation
        #  into the group 'func_params'
        traj.f_add_parameter('func_params.sigma', 10.0)
        traj.f_add_parameter('func_params.beta', 8.0/3.0)
        traj.f_add_parameter('func_params.rho', 28.0)
    elif traj.diff_name == 'diff_roessler':
        # If we use the Roessler system (https://en.wikipedia.org/wiki/R%C3%B6ssler_attractor)
        # we need different parameters
        traj.f_add_parameter('func_params.a', 0.1)
        traj.f_add_parameter('func_params.c', 14.0)
    else:
        raise ValueError('I don\'t know what %s is.' % traj.diff_name)



# We need to define the Roessler function, we will assume that the value array is 3 dimensional,
# first dimension is x-component, second y-component, and third the z-component
def diff_roessler(value_array, a, c):
    b=a
    diff_array = np.zeros(3)
    diff_array[0] = -value_array[1] - value_array[2]
    diff_array[1] = value_array[0] + a * value_array[1]
    diff_array[2] = b + value_array[2] * (value_array[0] - c)

    return diff_array


# And here goes our main function
def main():


    env = Environment(trajectory='Example_06_Euler_Integration',
                      filename='experiments/example_06/HDF5/example_06.hdf5',
                      file_title='Example_06_Euler_Integration',
                      log_folder='experiments/example_06/LOGS/',
                      comment = 'Go for Euler!')


    traj = env.v_trajectory

    # 1st  phase parameter addition
    # Remember we have some control flow in the add_parameters function, the default parameter
    # set we choose is the `'diff_loren'` one, but we want to deviate from that and use the
    # `'diff_roesler'`, so we can preset the corresponding name parameter to change the
    # control flow:
    traj.f_preset_parameter('diff_name', 'diff_roessler') # If you erase this line, you will get
                                                          # again the lorenz attractor
    add_parameters(traj)

    # 2nd phase preparation
    # We will add the differential equation as a derived parameter
    if traj.diff_name=='diff_lorenz':
        traj.f_add_derived_parameter(FunctionParameter,'diff_eq', diff_lorenz,
                                     comment='Source code of our equation!')

        diff_eqs = diff_lorenz
    elif traj.diff_name=='diff_roessler':
        traj.f_add_derived_parameter(FunctionParameter,'diff_eq', diff_roessler,
                                     comment='Source code of our equation!')

        diff_eqs = diff_roessler
    else:
        raise ValueError('I don\'t know what %s is.' % traj.diff_name)

    # We want to explore some initial conditions
    traj.f_explore({'initial_conditions' : [
        np.array([0.01,0.01,0.01]),
        np.array([2.02,0.02,0.02]),
        np.array([42.0,4.2,0.42])
    ]})
    # 3 different conditions are enough for now, I am tired of typing

    # 3rd phase let's run the experiment
    # We pass 'euler_scheme' as our top-level simulation functions and
    # the lorenz equation 'diff_lorenz' as an additional argument
    env.f_run(euler_scheme,diff_eqs)


    # 4th phase post-processing.
    # I would recommend post-processing completely independent from the simulation
    # but for simplicity let's do it here.
    # We won't reload the trajectory this time but simply update the skeleton
    traj.f_update_skeleton()

    #For the fun of it, let's print the source code
    print '\n ---------- The source code of your function ---------- \n %s' % traj.diff_eq


    # Let's get the exploration array:
    initial_conditions_exploration_array = traj.f_get('initial_conditions').f_get_array()
    # Now let's plot our simulated equations for the different initial conditions:
    # We will iterate through the run names
    for idx,run_name in enumerate(traj.f_get_run_names()):

        #Get the result of run idx from the trajectory
        euler_result = traj.results.f_get(run_name).euler_evolution
        # Now we manually need to load the result. Actually the results are not so large and we
        # could load them all at once, but for demonstration we do as if they were huge:
        traj.f_load_item(euler_result)
        euler_data = euler_result.data

        #Plot fancy 3d plot
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



if __name__ == '__main__':
    main()
