__author__ = 'robert'

import os

from pypet import Trajectory
import matplotlib.pyplot as plt


def main():

    # This time we don't need an environment since we just going to look
    # at data in the trajectory
    traj = Trajectory('FiringRate', add_time=False)

    # Let's load the trajectory from the file
    # Only load the parameters, we will load the results on the fly as we need them
    filename = os.path.join('hdf5', 'FiringRate.hdf5')
    traj.f_load(load_parameters=2, load_derived_parameters=0, load_results=0,
                load_other_data=0, filename=filename)

    # We'll simply use auto loading so all data will be loaded when needed.
    traj.v_auto_load = True

    rates_frame = traj.res.summary.firing_rates.rates_frame
    # Here we load the data automatically on the fly

    plt.figure()
    plt.subplot(2,1,1)
    #Let's iterate through the columns and plot the different firing rates :
    for tau_ref, I_col in rates_frame.iteritems():
        plt.plot(I_col.index, I_col, label='Avg. Rate for tau_ref=%s' % str(tau_ref))

    # Label the plot
    plt.xlabel('I')
    plt.ylabel('f[Hz]')
    plt.title('Firing as a function of input current `I`')
    plt.legend(loc='best')

    # Also let's plot an example run, how about run 13 ?
    example_run = 13

    traj.v_idx = example_run # We make the trajectory behave as a single run container.
    # This short statement has two major effects:
    # a) all explored parameters are set to the value of run 13,
    # b) if there are tree nodes with names other than the current run aka `run_00000013`
    # they are simply ignored, if we use the `$` sign or the `crun` statement,
    # these are translated into `run_00000013`.

    # Get the example data
    example_I = traj.I
    example_tau_ref = traj.tau_ref
    example_V = traj.results.neuron.crun.V # Here crun stands for run_00000013

    # We need the time step...
    dt = traj.dt
    # ...to create an x-axis for the plot
    dt_array = [irun * dt for irun in range(len(example_V))]

    # And plot the development of V over time,
    # Since this is rather repetitive, we only
    # plot the first eighth of it.
    plt.subplot(2,1,2)
    plt.plot(dt_array, example_V)
    plt.xlim((0, dt*len(example_V)/8))

    # Label the axis
    plt.xlabel('t[ms]')
    plt.ylabel('V')
    plt.title('Example of development of V for I=%s, tau_ref=%s in run %d' %
              (str(example_I), str(example_tau_ref), traj.v_idx))

    # And let's take a look at it
    plt.show()

    # Finally revoke the `traj.v_idx=13` statement and set everything back to normal.
    # Since our analysis is done here, we could skip that, but it is always a good idea
    # to do that.
    traj.f_restore_default()


if __name__ == '__main__':
    main()