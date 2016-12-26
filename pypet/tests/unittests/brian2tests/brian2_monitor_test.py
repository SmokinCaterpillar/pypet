__author__ = ['Henri Bunting', 'Robert Meyer']


import numpy as np

try:
    import brian2
    from brian2.monitors.spikemonitor import SpikeMonitor
    from brian2.monitors.statemonitor import StateMonitor
    from brian2.monitors.ratemonitor import PopulationRateMonitor
    from pypet.brian2.parameter import Brian2MonitorResult
except ImportError:
    brian2 = None

from pypet.tests.testutils.ioutils import unittest
from pypet.tests.unittests.parameter_test import ResultTest
from pypet.tests.unittests.brian2tests.run_a_brian2_network import run_network
import pypet.utils.comparisons as comp



@unittest.skipIf(brian2 is None, 'Can only be run with brian2!')
class Brian2MonitorTest(ResultTest):

    tags = 'unittest', 'brian2', 'result', 'monitor', 'henri'

    @classmethod
    def setUpClass(cls):
        if brian2 is not None:
            Brian2MonitorResult.monitors = run_network()

    def setUp(self):
        self.monitors = Brian2MonitorResult.monitors
        self.make_results()
        self.make_constructor()

    def make_constructor(self):
        self.Constructor=Brian2MonitorResult
        self.dynamic_imports = [Brian2MonitorResult]


    def check_spike_monitor(self, res, monitor):
        self.assertTrue(comp.nested_equal(monitor.num_spikes, res.num_spikes))
        self.assertTrue(comp.nested_equal(str(monitor.source), res.source))
        self.assertEqual(monitor.name,res.name)
        self.assertTrue(comp.nested_equal(monitor.t[:], res.t))
        self.assertTrue(comp.nested_equal(monitor.i[:], res.i))
        for idx, varname in enumerate(monitor.record_variables):
            self.assertTrue(comp.nested_equal(getattr(monitor, varname)[:], res.f_get(varname)))



    def check_state_monitor(self, res, monitor):
        self.assertEqual(monitor.record_variables, res.record_variables)
        self.assertEqual(monitor.name,res.name)

        times=np.array(monitor.t)
        if len(times)>0:
            self.assertTrue(comp.nested_equal(times, res.t))


        for idx, varname in enumerate(monitor.record_variables):
            self.assertTrue(comp.nested_equal(monitor.record, res.record))
            self.assertTrue(comp.nested_equal(monitor.when, res.when))
            self.assertTrue(comp.nested_equal(str(monitor.source), res.source))

            self.assertTrue(comp.nested_equal(getattr(monitor, varname), res.f_get(varname)))

    def check_population_rate_monitor(self, res, monitor):
        self.assertEqual(str(monitor.source),res.source)
        self.assertEqual(monitor.name,res.name)
        #self.assertTrue(comp.nested_equal(monitor._bin,res.bin))
        self.assertTrue(comp.nested_equal(monitor.rate[:],res.rate))
        self.assertTrue(comp.nested_equal(monitor.t[:],res.t))
        #self.assertTrue(comp.nested_equal(monitor.delay,res.delay))

    def test_failing_adding_another_monitor(self):

        for res in self.results.values():
            with self.assertRaises(TypeError):
                res.f_set(monitor=self.monitors.values()[0])


    def test_the_insertion_made_implicetly_in_setUp(self):

        for key, monitor in self.monitors.items():
            res = self.results[key]
            self.assertEqual(res.testtestextra, 42)
            self.assertEqual(res.v_monitor_type, monitor.__class__.__name__)


            if isinstance(monitor, SpikeMonitor):
                self.check_spike_monitor(res, monitor)

            elif isinstance(monitor, StateMonitor):
                self.check_state_monitor(res, monitor)

            elif  isinstance(monitor, PopulationRateMonitor):
                self.check_population_rate_monitor(res, monitor)

            else:
                raise ValueError('Monitor Type %s is not supported (yet)' % str(type(monitor)))

    def test_dir(self):
        res = self.results['SpikeMonitor']
        self.assertTrue('i' in res)
        self.assertTrue('i' in dir(res))

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
            self.results[key]=Brian2MonitorResult(key,monitor)

            self.results[key].f_set(testtestextra=42)
