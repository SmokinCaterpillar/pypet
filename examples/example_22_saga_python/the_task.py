__author__ = 'Robert Meyer'

import numpy as np
import inspect
import getopt
import sys

from pypet import Environment, Parameter, ArrayParameter, Trajectory


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


class FunctionParameter(Parameter):
    # We need to override the `f_set` function and simply extract the the source code if our
    # item is callable and store this instead.
    def f_set(self, data):
        if callable(data):
            data = inspect.getsource(data)
        return super(FunctionParameter, self).f_set(data)


def add_parameters(traj):
    """Adds all necessary parameters to the `traj` container"""

    traj.f_add_parameter('steps', 10000, comment='Number of time steps to simulate')
    traj.f_add_parameter('dt', 0.01, comment='Step size')

    # Here we want to add the initial conditions as an array parameter. We will simulate
    # a 3-D differential equation, the Lorenz attractor.
    traj.f_add_parameter(ArrayParameter,'initial_conditions', np.array([0.1,0.2,0.3]),
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


def get_batch():
    """Function that parses the batch id from the command line arguments"""
    optlist, args = getopt.getopt(sys.argv[1:], '', longopts='batch=')
    batch = 0
    for o, a in optlist:
        if o == '--batch':
            batch = int(a)
            print('Found batch %d' % batch)

    return batch


def explore_batch(traj, batch):
    """Chooses exploration according to `batch`"""
    explore_dict = {}
    explore_dict['sigma'] = np.arange(10.0 * batch, 10.0*(batch+1), 1.0).tolist()
    # for batch = 0 explores sigma in [0.0, 1.0, 2.0, ..., 9.0],
    # for batch = 1 explores sigma in [10.0, 11.0, 12.0, ..., 19.0]
    # and so on
    traj.f_explore(explore_dict)


# And here goes our main function
def main():
    batch = get_batch()

    filename = 'saga_%s.hdf5' % str(batch)
    env = Environment(trajectory='Example_22_Euler_Integration_%s' % str(batch),
                      filename=filename,
                      file_title='Example_22_Euler_Integration',
                      comment='Go for Euler!',
                      overwrite_file=True,
                      multiproc=True,  # Yes we can use multiprocessing within each batch!
                      ncores=4)

    traj = env.trajectory
    trajectory_name = traj.v_name

    # 1st a) phase parameter addition
    add_parameters(traj)

    # 1st b) phase preparation
    # We will add the differential equation (well, its source code only) as a derived parameter
    traj.f_add_derived_parameter(FunctionParameter,'diff_eq', diff_lorenz,
                                 comment='Source code of our equation!')

    # explore the trajectory
    explore_batch(traj, batch)

    # 2nd phase let's run the experiment
    # We pass `euler_scheme` as our top-level simulation function and
    # the Lorenz equation 'diff_lorenz' as an additional argument
    env.run(euler_scheme, diff_lorenz)


if __name__ == '__main__':
    main()
