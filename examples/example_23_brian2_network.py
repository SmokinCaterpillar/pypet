__author__ = 'Robert Meyer'

import logging
import os # For path names being viable under Windows and Linux

from pypet.environment import Environment
from pypet.brian2.parameter import Brian2Parameter, Brian2MonitorResult
from pypet.utils.explore import cartesian_product
# Don't do this at home:
from brian2 import pF, nS, mV, ms, nA, NeuronGroup, SpikeMonitor, StateMonitor, linspace,\
    Network

# We define a function to set all parameter
def add_params(traj):
    """Adds all necessary parameters to `traj`."""

    # We set the BrianParameter to be the standard parameter
    traj.v_standard_parameter=Brian2Parameter
    traj.v_fast_access=True

    # Add parameters we need for our network
    traj.f_add_parameter('Net.C',281*pF)
    traj.f_add_parameter('Net.gL',30*nS)
    traj.f_add_parameter('Net.EL',-70.6*mV)
    traj.f_add_parameter('Net.VT',-50.4*mV)
    traj.f_add_parameter('Net.DeltaT',2*mV)
    traj.f_add_parameter('Net.tauw',40*ms)
    traj.f_add_parameter('Net.a',4*nS)
    traj.f_add_parameter('Net.b',0.08*nA)
    traj.f_add_parameter('Net.I',.8*nA)
    traj.f_add_parameter('Net.Vcut','vm > 0*mV') # practical threshold condition
    traj.f_add_parameter('Net.N',50)

    eqs='''
    dvm/dt=(gL*(EL-vm)+gL*DeltaT*exp((vm-VT)/DeltaT)+I-w)/C : volt
    dw/dt=(a*(vm-EL)-w)/tauw : amp
    Vr:volt
    '''
    traj.f_add_parameter('Net.eqs', eqs)
    traj.f_add_parameter('reset', 'vm=Vr;w+=b')

# This is our job that we will execute
def run_net(traj):
    """Creates and runs BRIAN network based on the parameters in `traj`."""

    eqs=traj.eqs

    # Create a namespace dictionairy
    namespace = traj.Net.f_to_dict(short_names=True, fast_access=True)
    # Create the Neuron Group
    neuron=NeuronGroup(traj.N, model=eqs, threshold=traj.Vcut, reset=traj.reset,
                       namespace=namespace)
    neuron.vm=traj.EL
    neuron.w=traj.a*(neuron.vm-traj.EL)
    neuron.Vr=linspace(-48.3*mV,-47.7*mV,traj.N) # bifurcation parameter

    # Run the network initially for 100 milliseconds
    print('Initial Run')
    net = Network(neuron)
    net.run(100*ms, report='text') # we discard the first spikes

    # Create a Spike Monitor
    MSpike=SpikeMonitor(neuron)
    net.add(MSpike)
    # Create a State Monitor for the membrane voltage, record from neurons 1-3
    MStateV = StateMonitor(neuron, variables=['vm'],record=[1,2,3])
    net.add(MStateV)

    # Now record for 500 milliseconds
    print('Measurement run')
    net.run(500*ms,report='text')

    # Add the BRAIN monitors
    traj.v_standard_result = Brian2MonitorResult
    traj.f_add_result('SpikeMonitor',MSpike)
    traj.f_add_result('StateMonitorV', MStateV)


def main():
    # Let's be very verbose!
    logging.basicConfig(level = logging.INFO)


    # Let's do multiprocessing this time with a lock (which is default)
    filename = os.path.join('hdf5', 'example_23.hdf5')
    env = Environment(trajectory='Example_23_BRIAN2',
                      filename=filename,
                      file_title='Example_23_Brian2',
                      comment = 'Go Brian2!',
                      dynamically_imported_classes=[Brian2MonitorResult, Brian2Parameter])

    traj = env.trajectory

    # 1st a) add the parameters
    add_params(traj)

    # 1st b) prepare, we want to explore the different network sizes and different tauw time scales
    traj.f_explore(cartesian_product({traj.f_get('N').v_full_name:[50,60],
                           traj.f_get('tauw').v_full_name:[30*ms,40*ms]}))

    # 2nd let's run our experiment
    env.run(run_net)

    # You can take a look at the results in the hdf5 file if you want!

    # Finally disable logging and close all log-files
    env.disable_logging()


if __name__ == '__main__':
    main()



