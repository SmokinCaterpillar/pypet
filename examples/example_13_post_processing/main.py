__author__ = 'robert'

import numpy as np
import pandas as pd
import logging
import os # For path names working under Linux and Windows

from pypet import Environment, cartesian_product


def run_neuron(traj):
    """Runs a simulation of a model neuron.

    :param traj:

        Container with all parameters.

    :return:

        An estimate of the firing rate of the neuron

    """

    # Extract all parameters from `traj`
    V_init = traj.par.neuron.V_init
    I = traj.par.neuron.I
    tau_V = traj.par.neuron.tau_V
    tau_ref = traj.par.neuron.tau_ref
    dt = traj.par.simulation.dt
    duration = traj.par.simulation.duration

    steps = int(duration / float(dt))
    # Create some containers for the Euler integration
    V_array = np.zeros(steps)
    V_array[0] = V_init
    spiketimes = []  # List to collect all times of action potentials

    # Do the Euler integration:
    print('Starting Euler Integration')
    for step in range(1, steps):
        if V_array[step-1] >= 1:
            # The membrane potential crossed the threshold and we mark this as
            # an action potential
            V_array[step] = 0
            spiketimes.append((step-1)*dt)
        elif spiketimes and step * dt - spiketimes[-1] <= tau_ref:
            # We are in the refractory period, so we simply clamp the voltage
            # to 0
            V_array[step] = 0
        else:
            # Euler Integration step:
            dV = -1/tau_V * V_array[step-1] + I
            V_array[step] = V_array[step-1] + dV*dt

    print('Finished Euler Integration')

    # Add the voltage trace and spike times
    traj.f_add_result('neuron.$', V=V_array, nspikes=len(spiketimes),
                      comment='Contains the development of the membrane potential over time '
                              'as well as the number of spikes.')
    # This result will be renamed to `traj.results.neuron.run_XXXXXXXX`.

    # And finally we return the estimate of the firing rate
    return len(spiketimes) / float(traj.par.simulation.duration) *1000
    # *1000 since we have defined duration in terms of milliseconds


def neuron_postproc(traj, result_list):
    """Postprocessing, sorts computed firing rates into a table

    :param traj:

        Container for results and parameters

    :param result_list:

        List of tuples, where first entry is the run index and second is the actual
        result of the corresponding run.

    :return:
    """

    # Let's create a pandas DataFrame to sort the computed firing rate according to the
    # parameters. We could have also used a 2D numpy array.
    # But a pandas DataFrame has the advantage that we can index into directly with
    # the parameter values without translating these into integer indices.
    I_range = traj.par.neuron.f_get('I').f_get_range()
    ref_range = traj.par.neuron.f_get('tau_ref').f_get_range()

    I_index = sorted(set(I_range))
    ref_index = sorted(set(ref_range))
    rates_frame = pd.DataFrame(columns=ref_index, index=I_index)
    # This frame is basically a two dimensional table that we can index with our
    # parameters

    # Now iterate over the results. The result list is a list of tuples, with the
    # run index at first position and our result at the second
    for result_tuple in result_list:
        run_idx = result_tuple[0]
        firing_rates = result_tuple[1]
        I_val = I_range[run_idx]
        ref_val = ref_range[run_idx]
        rates_frame.loc[I_val, ref_val] = firing_rates # Put the firing rate into the
        # data frame

    # Finally we going to store our new firing rate table into the trajectory
    traj.f_add_result('summary.firing_rates', rates_frame=rates_frame,
                      comment='Contains a pandas data frame with all firing rates.')


def add_parameters(traj):
    """Adds all parameters to `traj`"""
    print('Adding Parameters')

    traj.f_add_parameter('neuron.V_init', 0.0,
                         comment='The initial condition for the '
                                    'membrane potential')
    traj.f_add_parameter('neuron.I', 0.0,
                         comment='The externally applied current.')
    traj.f_add_parameter('neuron.tau_V', 10.0,
                         comment='The membrane time constant in milliseconds')
    traj.f_add_parameter('neuron.tau_ref', 5.0,
                        comment='The refractory period in milliseconds '
                                'where the membrane potnetial '
                                'is clamped.')

    traj.f_add_parameter('simulation.duration', 1000.0,
                         comment='The duration of the experiment in '
                                'milliseconds.')
    traj.f_add_parameter('simulation.dt', 0.1,
                         comment='The step size of an Euler integration step.')


def add_exploration(traj):
    """Explores different values of `I` and `tau_ref`."""

    print('Adding exploration of I and tau_ref')

    explore_dict = {'neuron.I': np.arange(0, 1.01, 0.01).tolist(),
                    'neuron.tau_ref': [5.0, 7.5, 10.0]}

    explore_dict = cartesian_product(explore_dict, ('neuron.tau_ref', 'neuron.I'))
    # The second argument, the tuple, specifies the order of the cartesian product,
    # The variable on the right most side changes fastest and defines the
    # 'inner for-loop' of the cartesian product

    traj.f_explore(explore_dict)


def main():

    filename = os.path.join('hdf5', 'FiringRate.hdf5')
    env = Environment(trajectory='FiringRate',
                      comment='Experiment to measure the firing rate '
                            'of a leaky integrate and fire neuron. '
                            'Exploring different input currents, '
                            'as well as refractory periods',
                      add_time=False, # We don't want to add the current time to the name,
                      log_stdout=True,
                      log_config='DEFAULT',
                      multiproc=True,
                      ncores=2, #My laptop has 2 cores ;-)
                      wrap_mode='QUEUE',
                      filename=filename,
                      overwrite_file=True)

    traj = env.trajectory

    # Add parameters
    add_parameters(traj)

    # Let's explore
    add_exploration(traj)

    # Ad the postprocessing function
    env.add_postprocessing(neuron_postproc)

    # Run the experiment
    env.run(run_neuron)

    # Finally disable logging and close all log-files
    env.disable_logging()

if __name__ == '__main__':
    main()
