__author__ = 'robert'

import numpy as np

def run_neuron(traj):

    steps = int(traj.par.simulation.duration / float(traj.par.simulation.dt))

    traj.f_add_derived_parameter('simulation.steps', steps, comment='The steps')
    # This derived parameter will be sorted into the branch
    # `traj.derived_parameters.runs.run_XXXXXXXXX.simulation.steps
    # (where XXXXXXXXX is the index of the current run like run_00000003)
    # since we did not use the `$` wildcard character.


    # Extract all parameters from `traj`
    V_init = traj.par.neuron.V_init
    V_array = np.zeros((1,steps))
    V_array[0] = V_init
    I = traj.par.neuron.I
    tau_V = traj.par.neuron.tau_V
    dt = traj.par.neuron.dt
    tau_ref = traj.par.neuron.tau_ref

    spike_times = []
    # Do the Euler integration:
    for step in range(1, steps):
        if V_array[step-1] >= 1:
            # The membrane potential crossed the threshold and we mark this as
            # an action potential
            V_array[step] = 0
            spike_times.append((step-1)*dt)
        elif spike_times and step * dt - spike_times[-1] <= tau_ref:
            # We are in the refractory period, so we simply clamp the voltage
            # to 0
            V_array[step] = 0
        else:
            # Euler Integration step:
            dV = -1/tau_V * V_array[step-1] + I
            V_array[step] = V_array[step-1] + dV*dt

    # Add the voltage trace and spike times
    traj.f_add_result('neuron.$', V=V_array, spike_times = spike_times,
                      comment='Contains the development of the membrane potential over time '
                              'as well as a list of spike times.')
    # In contrast to the derived parameter above this result will be named
    # `traj.results.neuron.run_XXXXXXXXX` and not `traj.results.runs.run_XXXXXXXXX.neuron`.

    # And finally we return the estimate of the firing rate
    return len(spike_times) / float(traj.par.simulation.duration)


def neuron_postproc(traj, result_list, )