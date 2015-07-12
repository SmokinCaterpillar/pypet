import matplotlib.pyplot as plt

def plot_data(traj):
    traj.f_load(load_data=2)
    plt.subplot(1,2,1)
    spikes = traj.res.runs.r_0.spikes.spikes
    plt.scatter(spikes['spiketimes'], spikes['neuron'])
    plt.title('Spikes of first run')
    plt.subplot(1,2,2)
    for name in traj.f_iter_runs():
        voltage = traj.res.crun.v.v_values[0, :]
        times = traj.res.crun.v.times
        plt.plot(times, voltage)
    plt.title('Voltage trace of different runs')
    plt.show()


from brian2 import *
from pypet import Environment
from pypet.brian2.parameter import Brian2Parameter, Brian2MonitorResult

def run_network(traj):
    """Runs brian network consisting of 
        200 inhibitory IF neurons"""
    
    eqs = '''
    dv/dt=(v0-v)/(5*ms) : volt (unless refractory)
    v0 : volt
    '''
    group = NeuronGroup(200, model=eqs, threshold='v>10 * mV',
                        reset='v = 0*mV', refractory=5*ms)
    group.v0 = traj.par.v0
    group.v = np.random.rand(200) * 10.0 * mV

    syn = Synapses(group, group, pre='v-=1*mV')
    syn.connect('i != j', p=0.2)

    spike_monitor = SpikeMonitor(group)
    voltage_monitor = StateMonitor(group, 'v', record=True)

    run(0.25*second, report='text')

    traj.f_add_result(Brian2MonitorResult, 'spikes',
                      spike_monitor)
    traj.f_add_result(Brian2MonitorResult, 'v',
                      voltage_monitor)

env = Environment(dynamic_imports=[Brian2Parameter, Brian2MonitorResult])
traj = env.v_traj
traj.f_add_parameter(Brian2Parameter, 'v0', 0.0*mV,
                     comment='Input bias')
traj.f_explore({'v0': [11*mV, 13*mV, 15*mV]})
env.f_run(run_network)
plot_data(traj)
