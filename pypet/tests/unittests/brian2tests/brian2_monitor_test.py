__author__ = 'Henri Bunting'

from pypet.brian2.parameter import Brian2MonitorResult
from pypet.tests.unittests.parameter_test import ResultTest
from pypet.tests.unittests.brian2tests.run_a_brian2_network import run_network
import pypet.utils.comparisons as comp
from brian2.monitors.spikemonitor import SpikeMonitor
import numpy as np
import pandas as pd


class Brian2MonitorTest(ResultTest):

    tags = 'unittest', 'brian', 'result', 'monitor'

    @classmethod
    def setUpClass(cls):
        Brian2MonitorResult.monitors = run_network()
        pass

    '''
    @classmethod
    def tearDownClass(cls):
        reload(brian2)
    '''

    def setUp(self):
        self.monitors = Brian2MonitorResult.monitors
        self.make_results()
        self.make_constructor()


    def check_spike_monitor(self, res, monitor):
        #self.assertTrue(comp.nested_equal(monitor.delay, res.delay))
        self.assertTrue(comp.nested_equal(monitor.num_spikes, res.num_spikes))
        self.assertTrue(comp.nested_equal(str(monitor.source), res.source))


        self.assertEqual('second', res.spiketimes_unit)

        if res.v_storage_mode == Brian2MonitorResult.TABLE_MODE:
            spike_frame = res.spikes
            spiked_list=sorted(list(set(spike_frame['neuron'].to_dict().values())))
            self.assertEqual(spiked_list, res.neurons_with_spikes)
            print "restype:"+str(res.htype)
            #print "monitortype:"+str(monitor.htype)
            print res.spikes
            for idx, val_tuple in enumerate(zip(monitor.i, monitor.t_)):
                #print "idx:" +str(idx) + " val_tuple:"+str(val_tuple)
                neuron = val_tuple[0]
                time = val_tuple[1]
                vals = val_tuple[2:]

                self.assertEqual(neuron, spike_frame['neuron'][idx])

                self.assertEqual(float(time), spike_frame['spiketimes'][idx])


        elif res.v_storage_mode == Brian2MonitorResult.ARRAY_MODE:

            self.assertTrue('%0' in res.format_string and 'd' in res.format_string)

            zipped = zip(monitor.i, monitor.t_)
            dataframe = pd.DataFrame(data=zipped)
            #print dataframe[dataframe[0] == 3][1].tolist()
            neurons = [spike_num for spike_num in range(0, len(monitor.count))]
            spikes_by_neuron = dict()
            for neuron_num in neurons:
                spikes_by_neuron[neuron_num] = dataframe[dataframe[0] == neuron_num][1].tolist()
            print "a times:"+str(spikes_by_neuron[8])
            print "a res[spiketimes_08]:"+str(res['spiketimes_08'])

            spiked_set=set()
            for item_name in res:

                print "b name:"+str(item_name)

                if item_name.startswith('spiketimes') and not item_name.endswith('unit'):
                    neuron_id = int(item_name.split('_')[-1])
                    spiked_set.add(neuron_id)

                    #times = monitor.spiketimes[neuron_id]
                    times = spikes_by_neuron[neuron_id]
                    print "b#:"+str(neuron_id)
                    print "b times:"+str(times)
                    print "b res["+str(item_name)+"]:"+str(res[item_name])
                    self.assertTrue(comp.nested_equal(times,res[item_name]))

            spiked_list = sorted(list(spiked_set))
            self.assertEqual(spiked_list, res.neurons_with_spikes)
        else:
            raise RuntimeError('You shall not pass!')



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

            elif isinstance(monitor, MultiStateMonitor):
                self.check_multi_state_monitor(res, monitor)

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
