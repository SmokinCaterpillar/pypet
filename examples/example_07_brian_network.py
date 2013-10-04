__author__ = 'robert'

from pypet.environment import Environment
from pypet.brian.parameter import BrianParameter,BrianMonitorResult
from pypet.utils.explore import cartesian_product
# This is bad style I know, I'll make that better next time:
from brian import *
import logging

# Again we define a function to set all parameter
def add_params(traj):

    # We set the Brian Parameter to be the standard parameter
    traj.v_standard_parameter=BrianParameter
    traj.v_fast_access=True

    traj.f_add_parameter('Sim.defaultclock', 0.01*ms)
    traj.f_add_parameter('Net.C',281*pF)
    traj.f_add_parameter('Net.gL',30*nS)
    traj.f_add_parameter('Net.EL',-70.6*mV)
    traj.f_add_parameter('Net.VT',-50.4*mV)
    traj.f_add_parameter('Net.DeltaT',2*mV)
    traj.f_add_parameter('Net.tauw',40*ms)
    traj.f_add_parameter('Net.a',4*nS)
    traj.f_add_parameter('Net.b',0.08*nA)
    traj.f_add_parameter('Net.I',.8*nA)
    traj.f_add_parameter('Net.Vcut',traj.VT+5*traj.DeltaT) # practical threshold condition
    traj.f_add_parameter('Net.N',100)

    eqs="""
    dvm/dt=(gL*(EL-vm)+gL*DeltaT*exp((vm-VT)/DeltaT)+I-w)/C : volt
    dw/dt=(a*(vm-EL)-w)/tauw : amp
    Vr:volt
    """


    traj.f_add_parameter('Net.eqs', eqs)
    traj.f_add_parameter('reset', 'vm=Vr;w+=b')

# This is our job that we will execute
def run_net(traj):

    defaultclock.dt=traj.defaultclock

    # We let brian grasp the stuff from the local namespace, it's awful, I will change this example
    # soon:
    C=traj.C
    gL=traj.gL
    EL=traj.EL
    VT=traj.VT
    DeltaT=traj.DeltaT
    tauw=traj.tauw
    a=traj.a
    b=traj.b
    I=traj.I
    Vcut=traj.Vcut# practical threshold condition
    N=traj.N

    eqs=traj.eqs

    #Create the Neuron Group
    neuron=NeuronGroup(N,model=eqs,threshold=Vcut,reset=traj.reset)
    neuron.vm=EL
    neuron.w=a*(neuron.vm-EL)
    neuron.Vr=linspace(-48.3*mV,-47.7*mV,N) # bifurcation parameter

    #Run the brian stuff initially for 100 milliseconds
    run(100*msecond,report='text') # we discard the first spikes

    # Create a Spike Monitor
    MSpike=SpikeMonitor(neuron, delay = 1*ms) # record Vr and w at spike times
    #Create a State Monitor for the membrane voltage, record from neurons 1-3
    MStateV = StateMonitor(neuron,'vm',record=[1,2,3])


    # Now record for real for 500 milliseconds
    run(500*msecond,report='text')

    # Add the brian monitor
    traj.v_standard_result = BrianMonitorResult
    traj.f_add_result('SpikeMonitor',MSpike)
    traj.f_add_result('StateMonitorV', MStateV)




def main():
    # Let's be very verbose!
    logging.basicConfig(level = logging.DEBUG)


    env = Environment(trajectory='Example_07_BRIAN',
                      filename='experiments/example_07/HDF5/example_07.hdf5',
                      file_title='Example_07_Euler_Integration',
                      log_folder='experiments/example_07/LOGS/',
                      comment = 'Go Brian!',
                      dynamically_imported_classes=[BrianMonitorResult,BrianParameter])

    traj = env.v_trajectory

    #Let's to multiprocessing this time with a lock (which is default)
    traj.multiproc = 1
    traj.ncores= 2


    # 1st Add the parameters
    add_params(traj)

    # 2nd prepare, we want to explore the different network sizes and different tauw time scales
    traj.f_explore(cartesian_product({traj.f_get('N').v_full_name:[50,60],
                           traj.f_get('tauw').v_full_name:[30*ms,40*ms]}))

    # 3rd let's run our experiment
    env.f_run(run_net)


    #You can take a look at the results in the hdf5 file if you want!


if __name__ == '__main__':
    main()



