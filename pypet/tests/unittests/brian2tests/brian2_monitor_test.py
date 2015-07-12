__author__ = 'Henri Bunting'

from pypet.brian2.parameter import Brian2MonitorResult
from pypet.parameter import ObjectTable
from pypet.tests.unittests.parameter_test import ResultTest
from pypet.tests.unittests.brian2tests.run_a_brian2_network import run_network
import pypet.utils.comparisons as comp
from brian2.monitors.spikemonitor import SpikeMonitor
from brian2.monitors.statemonitor import StateMonitor
import numpy as np
import pandas as pd


class Brian2MonitorTest(ResultTest):

    tags = 'unittest', 'brian2', 'result', 'monitor', 'henri'

    @classmethod
    def setUpClass(cls):
        Brian2MonitorResult.monitors = run_network()
        pass

    def setUp(self):
        self.monitors = Brian2MonitorResult.monitors
        self.make_results()
        self.make_constructor()


    def check_spike_monitor(self, res, monitor):
        self.assertTrue(comp.nested_equal(monitor.num_spikes, res.num_spikes))
        self.assertTrue(comp.nested_equal(str(monitor.source), res.source))

        self.assertEqual('second', res.spiketimes_unit)

        if res.v_storage_mode == Brian2MonitorResult.TABLE_MODE:
            spike_frame = res.spikes
            spiked_list = sorted(list(set(spike_frame['neuron'].to_dict().values())))
            self.assertEqual(spiked_list, res.neurons_with_spikes)

            for idx, val_tuple in enumerate(zip(monitor.i, monitor.t_)):
                neuron = val_tuple[0]
                time = val_tuple[1]

                self.assertEqual(neuron, spike_frame['neuron'][idx])

                self.assertEqual(float(time), spike_frame['spiketimes'][idx])


        elif res.v_storage_mode == Brian2MonitorResult.ARRAY_MODE:

            self.assertTrue('%0' in res.format_string and 'd' in res.format_string)

            dataframe = pd.DataFrame(data=list(zip(monitor.i, monitor.t_)))
            neurons = [spike_num for spike_num in range(0, len(monitor.count))]
            spikes_by_neuron = dict()
            for neuron_num in neurons:
                spikes_by_neuron[neuron_num] = dataframe[dataframe[0] == neuron_num][1].tolist()

            spiked_set=set()
            for item_name in res:

                if item_name.startswith('spiketimes') and not item_name.endswith('unit'):
                    neuron_id = int(item_name.split('_')[-1])
                    spiked_set.add(neuron_id)

                    times = spikes_by_neuron[neuron_id]
                    self.assertTrue(comp.nested_equal(times, res[item_name]))

            spiked_list = sorted(list(spiked_set))
            self.assertEqual(spiked_list, res.neurons_with_spikes)
        else:
            raise RuntimeError('You shall not pass!')


    def check_state_monitor(self, res, monitor):
        self.assertEqual(monitor.record_variables, res.vars)

        times=np.array(monitor.t_)
        if len(times)>0:
            self.assertTrue(comp.nested_equal(times, res.times))


        for idx, varname in enumerate(monitor.record_variables):
            self.assertTrue(comp.nested_equal(monitor.record, res.record))
            self.assertTrue(comp.nested_equal(monitor.when, res.when))
            self.assertTrue(comp.nested_equal(str(monitor.source), res.source))

            self.assertTrue(comp.nested_equal(getattr(monitor, varname), res.f_get(varname+'_values')))



    def test_failing_adding_another_monitor_or_changing_the_mode(self):

        for res in self.results.values():
            with self.assertRaises(TypeError):
                res.f_set(monitor=self.monitors.values()[0])

        for res in self.results.values():
            with self.assertRaises(TypeError):
                res.v_storage_mode=Brian2MonitorResult.ARRAY_MODE

    def test_the_insertion_made_implicetly_in_setUp(self):

        for key, monitor in self.monitors.items():
            res = self.results[key]
            self.assertEqual(res.testtestextra, 42)
            self.assertEqual(res.v_monitor_type, monitor.__class__.__name__)


            if isinstance(monitor, SpikeMonitor):
                self.check_spike_monitor(res, monitor)

            elif isinstance(monitor, StateMonitor):
                self.check_state_monitor(res, monitor)

            else:
                raise ValueError('Monitor Type %s is not supported (yet)' % str(type(monitor)))

            '''
            elif isinstance(monitor, VanRossumMetric):
                self.check_van_rossum_metric(res, monitor)

            elif isinstance(monitor, PopulationSpikeCounter):
                self.check_population_spike_counter(res, monitor)

            elif isinstance(monitor, StateSpikeMonitor):
                self.check_state_spike_monitor(res, monitor)

            elif  isinstance(monitor, PopulationRateMonitor):
                self.check_population_rate_monitor(res, monitor)


            elif isinstance(monitor, ISIHistogramMonitor):
                self.check_isi_hist_monitor(res, monitor)

            elif isinstance(monitor, SpikeCounter):
                self.check_spike_counter(res, monitor)

            elif isinstance(monitor,StateMonitor):
                self.check_state_monitor(res, monitor)
            '''



    def test_dir(self):
        res = self.results['SpikeMonitor']
        self.assertTrue('spikes' in res)
        self.assertTrue('spikes' in dir(res))

    def test_set_item_via_number(self):
        res = self.results['SpikeMonitor']
        res[0] = 'Hi'
        res[777] = 777

        self.assertTrue(getattr(res, res.v_name) == 'Hi')
        self.assertTrue(res.f_get(0) == 'Hi')
        self.assertTrue(getattr(res, res.v_name + '_777') == 777)
        self.assertTrue(res[777] == 777)
        self.assertTrue(res.f_get(777) == 777)

        self.assertTrue(0 in res)
        self.assertTrue(777 in res)
        self.assertTrue(99999999 not in res)

        del res[0]
        self.assertTrue(0 not in res)

        del res[777]
        self.assertTrue(777 not in res)

    def make_results(self):
        self.results={}
        for key,monitor in self.monitors.items():
            if key.endswith('Ar'):
                self.results[key]=Brian2MonitorResult(key,monitor,
                                                     storage_mode=Brian2MonitorResult.ARRAY_MODE)
            else:
                self.results[key]=Brian2MonitorResult(key,monitor)

            self.results[key].f_set(testtestextra=42)
