__author__ = ['Henri Bunting', 'Robert Meyer']


import numpy as np
import time
import os

try:
    import brian2
    from brian2 import NeuronGroup, Synapses, SpikeMonitor, StateMonitor, mV, ms, Network, second, \
        PopulationRateMonitor
    from pypet.brian2.parameter import Brian2Parameter, Brian2MonitorResult
    from brian2 import prefs
    prefs.codegen.target = 'numpy'
except ImportError:
    brian2 = None

from pypet import Environment
from pypet.tests.testutils.data import TrajectoryComparator
from pypet.tests.testutils.ioutils import make_temp_dir, make_trajectory_name, get_log_config, \
    parse_args, run_suite, unittest


def run_network(traj):
    """Runs brian network consisting of
        200 inhibitory IF neurons"""

    eqs = '''
    dv/dt=(v0-v)/(5*ms) : volt (unless refractory)
    v0 : volt
    '''
    group = NeuronGroup(100, model=eqs, threshold='v>10 * mV',
                        reset='v = 0*mV', refractory=5*ms)
    group.v0 = traj.par.v0
    group.v = np.random.rand(100) * 10.0 * mV

    syn = Synapses(group, group, on_pre='v-=1*mV')
    syn.connect('i != j', p=0.2)

    spike_monitor = SpikeMonitor(group, variables=['v'])
    voltage_monitor = StateMonitor(group, 'v', record=True)
    pop_monitor = PopulationRateMonitor(group, name='pop' + str(traj.v_idx))

    net = Network(group, syn, spike_monitor, voltage_monitor, pop_monitor)
    net.run(0.25*second, report='text')

    traj.f_add_result(Brian2MonitorResult, 'spikes',
                      spike_monitor)
    traj.f_add_result(Brian2MonitorResult, 'v',
                      voltage_monitor)
    traj.f_add_result(Brian2MonitorResult, 'pop',
                      pop_monitor)


@unittest.skipIf(brian2 is None, 'Can only be run with brian2!')
class Brian2FullNetworkTest(TrajectoryComparator):

    tags = 'integration', 'brian2', 'parameter', 'network', 'hdf5', 'henri'

    def get_data(self, traj):
        traj.f_load(load_data=2)
        #plt.subplot(1,2,1)

        #plt.scatter(spikes.t, spikes.i)
        #plt.title('Spikes of first run')
        #plt.subplot(1,2,2)
        for name in traj.f_iter_runs():
            spikes = traj.res.runs[name].spikes
            self.assertTrue(len(spikes.t) > 0)
            self.assertTrue(len(spikes.i) > 0)
            self.assertTrue(len(spikes.v) > 0)
            voltage = traj.res.crun.v.v[0, :]
            times = traj.res.crun.v.t
            self.assertTrue(len(voltage) > 0)
            self.assertTrue(len(times) > 0)
            pop = traj.res.runs[name].pop
            self.assertTrue(len(pop.rate) >0)
            #plt.plot(times, voltage)
        #plt.title('Voltage trace of different runs')
        #plt.show()


    def test_net(self):
        env = Environment(trajectory='Test_'+repr(time.time()).replace('.','_'),
                          filename=make_temp_dir(os.path.join(
                              'experiments',
                              'tests',
                              'briantests',
                              'HDF5',
                               'briantest.hdf5')),
                          file_title='test',
                          log_config=get_log_config(),
                          dynamic_imports=['pypet.brian2.parameter.Brian2Parameter',
                                                        Brian2MonitorResult],
                          multiproc=False)
        traj = env.v_traj
        traj.f_add_parameter(Brian2Parameter, 'v0', 0.0*mV,
                             comment='Input bias')
        traj.f_explore({'v0': [11*mV, 13*mV, 15*mV]})
        env.f_run(run_network)
        self.get_data(traj)



if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)