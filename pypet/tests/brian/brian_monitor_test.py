from brian import SpikeCounter
from pypet.brian.parameter import BrianMonitorResult
from pypet.tests.parameter_test import ResultTest

__author__ = 'Robert Meyer'

from pypet.tests.brian.run_a_brian_network import run_network
import pypet.utils.comparisons as comp

from brian.monitor import SpikeMonitor,SpikeCounter,StateMonitor, \
    PopulationSpikeCounter, PopulationRateMonitor, StateSpikeMonitor,  \
        MultiStateMonitor, ISIHistogramMonitor, VanRossumMetric, Monitor

from brian.fundamentalunits import Unit, Quantity, get_unit, get_unit_fast





class BrianMonitorTest(ResultTest):

    @classmethod
    def setUpClass(BrianMonitorTest):
        BrianMonitorResult.monitors=run_network()

    def setUp(self):
        self.monitors = BrianMonitorResult.monitors
        self.make_results()

    def make_constructor(self):
        pass

    def check_spike_counter(self, res, monitor):
        self.assertTrue(comp.nested_equal(monitor.count, res.count))
        self.assertTrue(comp.nested_equal(monitor.nspikes, res.nspikes))
        self.assertTrue(comp.nested_equal(str(monitor.source), res.source))

    def check_van_rossum_metric(self,res, monitor):
        self.assertTrue(comp.nested_equal(float(monitor.tau), res.tau))
        self.assertTrue(comp.nested_equal('second', res.tau_unit))
        self.assertTrue(comp.nested_equal(monitor.distance, res.distance))
        self.assertTrue(comp.nested_equal(monitor.N, res.N))
        self.assertTrue(comp.nested_equal(str(monitor.source), res.source))

    def check_population_spike_counter(self, res, monitor):
        self.assertTrue(comp.nested_equal(monitor.delay, res.delay))
        self.assertTrue(comp.nested_equal(monitor.nspikes, res.nspikes))
        self.assertTrue(comp.nested_equal(str(monitor.source), res.source))

    def check_state_spike_monitor(self, res, monitor):
        self.assertTrue(comp.nested_equal(monitor.delay, res.delay))
        self.assertTrue(comp.nested_equal(monitor.nspikes, res.nspikes))
        self.assertTrue(comp.nested_equal(str(monitor.source), res.source))
        self.assertTrue(comp.nested_equal(monitor._varnames, res.varnames))



        if res.v_storage_mode == BrianMonitorResult.TABLE_MODE:
            spike_frame = res.spikes
            spiked_list=sorted(list(set(spike_frame['neuron'].to_dict().values())))
            self.assertEqual(spiked_list, res.neurons_with_spikes)
            for idx,val_tuple in enumerate(monitor.spikes):
                neuron = val_tuple[0]
                time = val_tuple[1]
                vals = val_tuple[2:]

                self.assertEqual(neuron, spike_frame['neuron'][idx])

                self.assertEqual(float(time), spike_frame['times'][idx])

                for idx_var, varname in enumerate(res.varnames):
                    val = vals[idx_var]
                    self.assertEqual(float(val),spike_frame[varname][idx_var])



        elif res.v_storage_mode == BrianMonitorResult.ARRAY_MODE:
            spiked_set=set()
            for item_name in res:

                if item_name.startswith('spiketimes'):
                    neuron_id = int(item_name.split('_')[-1])
                    spiked_set.add(neuron_id)

                    times = monitor.times(neuron_id)
                    self.assertTrue(comp.nested_equal(times,res[item_name]))

                for varname in res.varnames:
                    if item_name.startswith(varname) and not item_name.endswith('unit'):
                        neuron_id =int(item_name.split('_')[-1])
                        values = monitor.values(varname,neuron_id)


                        # Remove units:
                        self.assertTrue(comp.nested_equal(values,res[item_name]))

            spiked_list = sorted(list(spiked_set))
            self.assertEqual(spiked_list, res.neurons_with_spikes)
        else:
            raise RuntimeError('You shall not pass!')


        # Check Units
        for idx,varname in enumerate(monitor._varnames):
            unit = repr(get_unit_fast(monitor.spikes[0][idx+2]))
            self.assertTrue(unit,res[varname+'_unit'])



    def test_the_insertion_made_implicetly_in_setUp(self):

        for key,monitor in self.monitors.items():
            res = self.results[key]
            self.assertEqual(res.testtestextra,42)

            if isinstance(monitor, SpikeCounter):
                self.check_spike_counter(res, monitor)

            elif isinstance(monitor, VanRossumMetric):
                self.check_van_rossum_metric(res, monitor)

            elif isinstance(monitor, PopulationSpikeCounter):
                self.check_population_spike_counter(res, monitor)

            elif isinstance(monitor, StateSpikeMonitor):
                self.check_state_spike_monitor(res, monitor)

            # elif  isinstance(monitor, PopulationRateMonitor):
            #     self.check_population_rate_monitor(res, monitor)
            #
            #
            # elif isinstance(monitor, ISIHistogramMonitor):
            #     self.check_isi_hist_monitor(res, monitor)
            #
            # elif isinstance(monitor,SpikeMonitor):
            #     self.check_spike_monitor(res, monitor)
            #
            # elif isinstance(monitor, MultiStateMonitor):
            #     self.check_multi_state_monitor(res, monitor)
            #
            # elif isinstance(monitor,StateMonitor):
            #     self.check_state_monitor(res, monitor)
            #
            #
            # else:
            #     raise ValueError('Monitor Type %s is not supported (yet)' % str(type(monitor)))

    def make_results(self):
        self.results={}
        for key,monitor in self.monitors.iteritems():
            if key.endswith('Ar'):
                self.results[key]=BrianMonitorResult(key,monitor,
                                                     storage_mode=BrianMonitorResult.ARRAY_MODE)
            else:
                self.results[key]=BrianMonitorResult(key,monitor)

            self.results[key].f_set(testtestextra=42)

