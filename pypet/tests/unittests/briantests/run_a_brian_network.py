__author__ = 'Robert Meyer'

from brian import *

def run_network():

    clear(True, True)

    monitor_dict={}
    defaultclock.dt= 0.01*ms

    C=281*pF
    gL=30*nS
    EL=-70.6*mV
    VT=-50.4*mV
    DeltaT=2*mV
    tauw=40*ms
    a=4*nS
    b=0.08*nA
    I=8*nA
    Vcut=DeltaT# practical threshold condition
    N=10

    reset = 'vm=Vr;w+=b'

    eqs="""
    dvm/dt=(gL*(EL-vm)+gL*DeltaT*exp((vm-VT)/DeltaT)+I-w)/C : volt
    dw/dt=(a*(vm-EL)-w)/tauw : amp
    Vr:volt
    """

    neuron=NeuronGroup(N,model=eqs,threshold=Vcut,reset=reset)
    neuron.vm=EL
    neuron.w=a*(neuron.vm-EL)
    neuron.Vr=linspace(-48.3*mV,-47.7*mV,N) # bifurcation parameter

    #run(25*msecond,report='text') # we discard the first spikes

    MSpike=SpikeMonitor(neuron, delay = 1*ms) # record Vr and w at spike times
    MPopSpike =PopulationSpikeCounter(neuron, delay = 1*ms)
    MPopRate = PopulationRateMonitor(neuron,bin=5*ms)
    MStateV = StateMonitor(neuron,'vm',record=[1,2,3])
    MStatewMean = StateMonitor(neuron,'w',record=False)

    MRecentStateV = RecentStateMonitor(neuron,'vm',record=[1,2,3],duration=10*ms)
    MRecentStatewMean = RecentStateMonitor(neuron,'w',duration=10*ms,record=False)

    MCounts = SpikeCounter(neuron)

    MStateSpike = StateSpikeMonitor(neuron,('w','vm'))

    MMultiState = MultiStateMonitor(neuron,['w','vm'],record=[6,7,8,9])

    ISIHist = ISIHistogramMonitor(neuron,[0,0.0001,0.0002], delay = 1*ms)

    VanRossum = VanRossumMetric(neuron, tau=5*msecond)

    run(10*msecond,report='text')


    monitor_dict['SpikeMonitor']=MSpike
    monitor_dict['SpikeMonitorAr']=MSpike
    monitor_dict['PopulationSpikeCounter']=MPopSpike
    monitor_dict['PopulationRateMonitor']=MPopRate
    monitor_dict['StateMonitorV']=MStateV
    monitor_dict['StateMonitorwMean']=MStatewMean
    monitor_dict['Counts']=MCounts
    monitor_dict['StateSpikevmw']=MStateSpike
    monitor_dict['StateSpikevmwAr']=MStateSpike
    monitor_dict['MultiState']=MMultiState
    monitor_dict['ISIHistogrammMonitor']=ISIHist
    monitor_dict['RecentStateMonitorV']=MRecentStateV
    monitor_dict['RecentStateMonitorwMean']=MRecentStatewMean
    monitor_dict['VanRossumMetric']=VanRossum

    return monitor_dict