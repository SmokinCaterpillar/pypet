""" Module that shows how to wrap *pypet* around an existing project

Thanks to *pypet* the module is now very flexible.
You can immediately start exploring different sets
of parameters, like different seeds or cell numbers.
Accordingly, you can simply change ``exp_dict`` to explore different sets.

On the contrary, this is tedious in the original code
and requires some effort of refactoring.

"""

__author__ = 'Robert Meyer'

import os
import logging

from pypet import Environment, cartesian_product, progressbar, Parameter

# Lets import the stuff we already have:
from original import cellular_automaton_1D, make_initial_state, plot_pattern

def make_filename(traj):
    """ Function to create generic filenames based on what has been explored """
    explored_parameters = traj.f_get_explored_parameters()
    filename = ''
    for param in explored_parameters.values():
        short_name = param.v_name
        val = param.f_get()
        filename += '%s_%s__' % (short_name, str(val))

    return filename[:-2] + '.png' # get rid of trailing underscores and add file type

def wrap_automaton(traj):
    """ Simple wrapper function for compatibility with *pypet*.

    We will call the original simulation functions with data extracted from ``traj``.

    The resulting automaton patterns wil also be stored into the trajectory.

    :param traj: Trajectory container for data

    """
    # Make initial state
    initial_state = make_initial_state(traj.initial_name, traj.ncells, traj.seed)
    # Run simulation
    pattern = cellular_automaton_1D(initial_state, traj.rule_number, traj.steps)
    # Store the computed pattern
    traj.f_add_result('pattern', pattern, comment='Development of CA over time')


def main():
    """ Main *boilerplate* function to start simulation """
    # Now let's make use of logging
    logger = logging.getLogger()

    # Create folders for data and plots
    folder = os.path.join(os.getcwd(), 'experiments', 'ca_patterns_pypet')
    if not os.path.isdir(folder):
        os.makedirs(folder)
    filename = os.path.join(folder, 'all_patterns.hdf5')

    # Create an environment
    env = Environment(trajectory='cellular_automata',
                      multiproc=True,
                      ncores=4,
                      wrap_mode='QUEUE',
                      filename=filename,
                      overwrite_file=True)

    # extract the trajectory
    traj = env.traj

    traj.par.ncells = Parameter('ncells', 400, 'Number of cells')
    traj.par.steps = Parameter('steps', 250, 'Number of timesteps')
    traj.par.rule_number = Parameter('rule_number', 30, 'The ca rule')
    traj.par.initial_name = Parameter('initial_name', 'random', 'The type of initial state')
    traj.par.seed = Parameter('seed', 100042, 'RNG Seed')

    # Explore
    exp_dict = {'rule_number' : [10, 30, 90, 110, 184],
                'initial_name' : ['single', 'random'],}
    # # You can uncomment the ``exp_dict`` below to see that changing the
    # # exploration scheme is now really easy:
    # exp_dict = {'rule_number' : [10, 30, 90, 110, 184],
    #             'ncells' : [100, 200, 300],
    #             'seed': [333444555, 123456]}
    exp_dict = cartesian_product(exp_dict)
    traj.f_explore(exp_dict)

    # Run the simulation
    logger.info('Starting Simulation')
    env.run(wrap_automaton)

    # Load all data
    traj.f_load(load_data=2)

    logger.info('Printing data')
    for idx, run_name in enumerate(traj.f_iter_runs()):
        # Plot all patterns
        filename = os.path.join(folder, make_filename(traj))
        plot_pattern(traj.crun.pattern, traj.rule_number, filename)
        progressbar(idx, len(traj), logger=logger)

    # Finally disable logging and close all log-files
    env.disable_logging()


if __name__ == '__main__':
    main()