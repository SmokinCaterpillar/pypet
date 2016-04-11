__author__ = 'Robert Meyer'


from pypet.tests.testutils.ioutils import unittest, run_suite, make_temp_dir, get_log_config, \
    parse_args
from pypet.tests.testutils.data import TrajectoryComparator
from pypet import Environment
import time
import os
try:
    import brian
    from brian import ms, mV, NeuronGroup, Synapses, PopulationRateMonitor, SpikeMonitor, \
        StateMonitor, Network, Equations
    from pypet.brian import NetworkComponent, NetworkAnalyser, NetworkRunner, NetworkManager, \
        BrianResult, BrianParameter, BrianMonitorResult
except ImportError as e:
    brian = None
    NetworkComponent = object
    NetworkAnalyser = object


class TheNeurons(NetworkComponent):
    def __init__(self):
        self.pre_built = False

    def add_parameters(self, traj):
        traj.v_standard_parameter = BrianParameter
        traj.f_add_parameter('N', 100, comment='net size')
        traj.f_add_parameter('reset', 'v = 0*mV', comment='Neuron reset')
        traj.f_add_parameter('threshold', 'v>10 * mV', comment='Neuron threshold')
        traj.f_add_parameter('refr', 5*ms, comment='Neuron refractory')
        traj.f_add_parameter('tau', 5*ms, comment='Neuron time constant')
        traj.f_add_parameter('v00', 11*mV, comment='First input')
        traj.f_add_parameter('v01', 11*mV, comment='Second input')
        eqs = '''
            dv/dt=(v0-v)/(tau) : volt
            v0 : volt
            '''
        traj.f_add_parameter('model', eqs, comment='Model eqs')

    def build(self, traj, brian_list, network_dict):
        if not self.pre_built:
            eqs = Equations(traj.model, tau=traj.tau)
            ng = NeuronGroup(traj.N, eqs,
                             threshold=traj.threshold,
                             reset=traj.reset,
                             refractory=traj.refr)
            ng.v0 = traj.v00
            brian_list.append(ng)
            network_dict['group'] = ng

    def pre_build(self, traj, brian_list, network_dict):
        self.build(traj, brian_list, network_dict)
        self.pre_built = True

    def add_to_network(self, traj, network, current_subrun, subrun_list, network_dict):
        if current_subrun.v_annotations.order == 1:
            network.v0 = traj.v00


class TheConnection(NetworkComponent):
    def __init__(self):
        self.pre_built = False

    def add_parameters(self, traj):
        traj.f_add_parameter('pret', 'v += 1*mV', comment='net weight')
        traj.f_add_parameter('prob', 0.1, comment='Connection probability')

    def build(self, traj, brian_list, network_dict):
        if not self.pre_built:
            group = network_dict['group']
            syn = Synapses(group, group, pre='v-=1*mV')
            syn.connect_random(sparseness=traj.prob)
            brian_list.append(syn)
            network_dict['synapses'] = syn

    def pre_build(self, traj, brian_list, network_dict):
        self.build(traj, brian_list, network_dict)
        self.pre_built = True


class TheMonitors(NetworkAnalyser):
    def __init__(self):
        self.monitors = {}

    def add_to_network(self, traj, network, current_subrun, subrun_list, network_dict):
        if current_subrun.v_annotations.order == 0:
            prm = PopulationRateMonitor(network_dict['group'])
            self.monitors['prm'] = prm
            network.add(prm)
        elif current_subrun.v_annotations.order == 1:
            spm = SpikeMonitor(network_dict['group'])
            sm = StateMonitor(network_dict['group'], varname='v', record=True)
            self.monitors['spm'] = spm
            self.monitors['sm'] = sm
            network.add(spm)
            network.add(sm)

    def analyse(self, traj, network, current_subrun, subrun_list, network_dict):
        if current_subrun.v_annotations.order == 0:
            traj.f_add_result(BrianMonitorResult, 'prm', self.monitors['prm'])
            traj.f_add_result(BrianResult, 'dummy', 1*mV, comment='dummy')
        elif current_subrun.v_annotations.order == 1:
            traj.f_add_result(BrianMonitorResult, 'spm', self.monitors['spm'])
            traj.f_add_result(BrianMonitorResult, 'sm', self.monitors['sm'])

    def remove_from_network(self, traj, network, current_subrun, subrun_list, network_dict):
        if current_subrun.v_annotations.order == 0:
            network.remove(self.monitors['prm'])
        elif current_subrun.v_annotations.order == 1:
            network.remove(self.monitors['spm'])
            network.remove(self.monitors['sm'])


class TheSimulation(NetworkComponent):
    def add_parameters(self, traj):
        r0 = traj.f_add_parameter('simulation.pre_durations.r0', 100*ms)
        r0.v_annotations.order=0
        r1 = traj.f_add_parameter('simulation.durations.r1', 300*ms)
        r1.v_annotations.order=1


@unittest.skipIf(brian is None, "Can only be run with brian")
class BrainNetworkTest(TrajectoryComparator):

    tags = 'integration', 'brian', 'parameter', 'network', 'multiproc'


    def check_data(self, traj):
        traj.f_load(load_data=2)
        for name in traj.f_iter_runs():
            spikes = traj.res.runs[name].spm.nspikes
            self.assertTrue(spikes > 0)
            voltage = traj.res.crun.sm.values[0, :]
            times = traj.res.crun.sm.times
            self.assertTrue(len(voltage) > 0)
            self.assertTrue(len(times) > 0)

    def test_with_pre_run(self):
        runner = NetworkRunner()
        components = [TheNeurons(), TheConnection(), TheSimulation()]
        analyser = [TheMonitors()]
        nm = NetworkManager(network_runner=runner, component_list=components,
                            analyser_list=analyser)


        env = Environment(trajectory='Test_'+repr(time.time()).replace('.','_'),
                          filename=make_temp_dir(os.path.join(
                              'experiments',
                              'tests',
                              'briantests',
                              'HDF5',
                               'briantest.hdf5')),
                          file_title='test',
                          log_config=get_log_config(),
                          dynamic_imports=['pypet.brian2.parameter.BrianParameter',
                                                        BrianMonitorResult, BrianResult],
                          multiproc=True,
                          ncores=2)
        traj = env.v_traj
        nm.add_parameters(traj)
        traj.f_explore({'v01': [11*mV, 13*mV]})
        nm.pre_run_network(traj)

        env.f_run(nm.run_network)
        self.check_data(traj)

    def test_without_pre_run(self):
        runner = NetworkRunner()
        components = [TheNeurons(), TheConnection(), TheSimulation()]
        analyser = [TheMonitors()]
        nm = NetworkManager(network_runner=runner, component_list=components,
                            analyser_list=analyser)


        env = Environment(trajectory='Test_'+repr(time.time()).replace('.','_'),
                          filename=make_temp_dir(os.path.join(
                              'experiments',
                              'tests',
                              'briantests',
                              'HDF5',
                               'briantest.hdf5')),
                          file_title='test',
                          log_config=get_log_config(),
                          dynamic_imports=['pypet.brian2.parameter.BrianParameter',
                                                        BrianMonitorResult, BrianResult],
                          multiproc=True,
                          ncores=2)
        traj = env.v_traj
        nm.add_parameters(traj)
        traj.f_explore({'v01': [11*mV, 13*mV]})
        env.f_run(nm.run_network)
        self.check_data(traj)

if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)