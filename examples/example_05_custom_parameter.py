__author__ = 'Robert Meyer'

import numpy as np
import inspect
import os # For path names being viable under Windows and Linux

from pypet import Environment, Parameter, ArrayParameter, Trajectory
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D


# Here we will see how we can write our own custom parameters and how we can use
# it with a trajectory.

# Now we want to do a more sophisticated simulations, we will integrate a differential equation
# with an Euler scheme

# Let's first define our job to do
def euler_scheme(traj, diff_func):
    """Simulation function for Euler integration.

    :param traj:

        Container for parameters and results

    :param diff_func:

        The differential equation we want to integrate

    """

    steps = traj.steps
    initial_conditions = traj.initial_conditions
    dimension = len(initial_conditions)

    # This array will collect the results
    result_array = np.zeros((steps,dimension))
    # Get the function parameters stored into `traj` as a dictionary
    # with the (short) names as keys :
    func_params_dict = traj.func_params.f_to_dict(short_names=True, fast_access=True)
    # Take initial conditions as first result
    result_array[0] = initial_conditions

    # Now we compute the Euler Scheme steps-1 times
    for idx in range(1,steps):
        result_array[idx] = diff_func(result_array[idx-1], **func_params_dict) * traj.dt + \
                            result_array[idx-1]
    # Note the **func_params_dict unzips the dictionary, it's the reverse of **kwargs in function
    # definitions!

    #Finally we want to keep the results
    traj.f_add_result('euler_evolution', data=result_array, comment='Our time series data!')


# Ok, now we want to make our own (derived) parameter that stores source code of python functions.
# We do NOT want a parameter that stores an executable function. This would complicate
# the problem a lot. If you have something like that in mind, you might wanna take a look
# at the marshal (http://docs.python.org/2/library/marshal) module
# or dill (https://pypi.python.org/pypi/dill) package.
# Our intention here is to define a parameter that we later on use as a derived parameter
# to simply keep track of the source code we use ('git' would be, of course, the better solution
# but this is just an illustrative example)
class FunctionParameter(Parameter):
    # We need to override the `f_set` function and simply extract the the source code if our
    # item is callable and store this instead.
    def f_set(self, data):
        if callable(data):
            data = inspect.getsource(data)
        return super(FunctionParameter, self).f_set(data)

    # For more complicate parameters you might consider implementing:
    # `f_supports` (we do not need it since we convert the data to stuff the parameter already
    #    supports, and that is strings!)
    #
    # and
    # the private functions
    #
    # `_values_of_same_type` (to tell whether data is similar, i.e. of two data items agree in their
    #   type, this is important to only allow exploration within the same dimension.
    #   For instance, a parameter that stores integers, should only explore integers etc.)
    #
    # and
    #
    # `_equal_values` (to tell if two data items are equal. This is important for merging if you
    #       want to erase duplicate parameter points. The trajectory needs to know when a
    #       parameter space point was visited before.)
    #
    # and
    #
    # `_store` (to be able to turn complex data into basic types understood by the storage service)
    #
    # and
    #
    # `_load` (to be able to recover your complex data form the basic types understood by the storage
    # service)
    #
    # But for now we will rely on the parent functions and hope for the best!



# Ok now let's follow the ideas in the final section of the cookbook and let's
# have a part in our simulation that only defines the parameters.
def add_parameters(traj):
    """Adds all necessary parameters to the `traj` container"""

    traj.f_add_parameter('steps', 10000, comment='Number of time steps to simulate')
    traj.f_add_parameter('dt', 0.01, comment='Step size')

    # Here we want to add the initial conditions as an array parameter. We will simulate
    # a 3-D differential equation, the Lorenz attractor.
    traj.f_add_parameter(ArrayParameter,'initial_conditions', np.array([0.0,0.0,0.0]),
                         comment = 'Our initial conditions, as default we will start from'
                                   ' origin!')

    # We will group all parameters of the Lorenz differential equation into the group 'func_params'
    traj.f_add_parameter('func_params.sigma', 10.0)
    traj.f_add_parameter('func_params.beta', 8.0/3.0)
    traj.f_add_parameter('func_params.rho', 28.0)

    #For the fun of it we will annotate the  group
    traj.func_params.v_annotations.info='This group contains as default the original values chosen ' \
                                   'by Edward Lorenz in 1963. Check it out on wikipedia ' \
                                   '(https://en.wikipedia.org/wiki/Lorenz_attractor)!'


# We need to define the lorenz function, we will assume that the value array is 3 dimensional,
# First dimension contains the x-component, second y-component, and third the z-component
def diff_lorenz(value_array, sigma, beta, rho):
    """The Lorenz attractor differential equation

    :param value_array: 3d array containing the x,y, and z component values.
    :param sigma: Constant attractor parameter
    :param beta: FConstant attractor parameter
    :param rho: Constant attractor parameter

    :return: 3d array of the Lorenz system evaluated at `value_array`

    """
    diff_array = np.zeros(3)
    diff_array[0] = sigma * (value_array[1]-value_array[0])
    diff_array[1] = value_array[0] * (rho - value_array[2]) - value_array[1]
    diff_array[2] = value_array[0] * value_array[1] - beta * value_array[2]

    return diff_array


# And here goes our main function
def main():

    filename = os.path.join('hdf5', 'example_05.hdf5')
    env = Environment(trajectory='Example_05_Euler_Integration',
                      filename=filename,
                      file_title='Example_05_Euler_Integration',
                      overwrite_file=True,
                      comment='Go for Euler!')


    traj = env.trajectory
    trajectory_name = traj.v_name

    # 1st a) phase parameter addition
    add_parameters(traj)

    # 1st b) phase preparation
    # We will add the differential equation (well, its source code only) as a derived parameter
    traj.f_add_derived_parameter(FunctionParameter,'diff_eq', diff_lorenz,
                                 comment='Source code of our equation!')

    # We want to explore some initial conditions
    traj.f_explore({'initial_conditions' : [
        np.array([0.01,0.01,0.01]),
        np.array([2.02,0.02,0.02]),
        np.array([42.0,4.2,0.42])
    ]})
    # 3 different conditions are enough for an illustrative example

    # 2nd phase let's run the experiment
    # We pass `euler_scheme` as our top-level simulation function and
    # the Lorenz equation 'diff_lorenz' as an additional argument
    env.run(euler_scheme, diff_lorenz)

    # We don't have a 3rd phase of post-processing here

    # 4th phase analysis.
    # I would recommend to do post-processing completely independent from the simulation,
    # but for simplicity let's do it here.

    # Let's assume that we start all over again and load the entire trajectory new.
    # Yet, there is an error within this approach, do you spot it?
    del traj
    traj = Trajectory(filename=filename)

    # We will only fully load parameters and derived parameters.
    # Results will be loaded manually later on.
    try:
        # However, this will fail because our trajectory does not know how to
        # build the FunctionParameter. You have seen this coming, right?
        traj.f_load(name=trajectory_name, load_parameters=2, load_derived_parameters=2,
                    load_results=1)
    except ImportError as e:

        print('That did\'nt work, I am sorry: %s ' % str(e))

        # Ok, let's try again but this time with adding our parameter to the imports
        traj = Trajectory(filename=filename,
                           dynamically_imported_classes=FunctionParameter)

        # Now it works:
        traj.f_load(name=trajectory_name, load_parameters=2, load_derived_parameters=2,
                    load_results=1)


    #For the fun of it, let's print the source code
    print('\n ---------- The source code of your function ---------- \n %s' % traj.diff_eq)

    # Let's get the exploration array:
    initial_conditions_exploration_array = traj.f_get('initial_conditions').f_get_range()
    # Now let's plot our simulated equations for the different initial conditions:
    # We will iterate through the run names
    for idx, run_name in enumerate(traj.f_get_run_names()):

        #Get the result of run idx from the trajectory
        euler_result = traj.results.f_get(run_name).euler_evolution
        # Now we manually need to load the result. Actually the results are not so large and we
        # could load them all at once. But for demonstration we do as if they were huge:
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

    # You have to click through the images to stop the example_05 module!

    # Finally disable logging and close all log-files
    env.disable_logging()


if __name__ == '__main__':
    main()

