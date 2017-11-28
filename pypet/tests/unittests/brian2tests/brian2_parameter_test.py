__author__ = 'Henri Bunting'

import sys

import numpy as np
from pypet.parameter import BaseParameter

import unittest

try:
    import brian2
    from brian2.units.stdunits import mV, mA, kHz, ms
    from pypet.brian2.parameter import Brian2Parameter, Brian2Result, get_unit_fast
except ImportError:
    brian2 = None

from pypet.parameter import PickleParameter, ArrayParameter, SparseParameter
from pypet.tests.unittests.parameter_test import ParameterTest, ResultTest
from pypet.tests.testutils.ioutils import parse_args, run_suite
from pypet.utils.explore import cartesian_product

import logging
logging.basicConfig(level=logging.DEBUG)


@unittest.skipIf(brian2 is None, 'Can only be run with brian2!')
class Brian2ParameterTest(ParameterTest):

    tags = 'unittest', 'brian2', 'parameter', 'henri'

    def setUp(self):

        if not hasattr(self, 'data'):
            self.data = {}

        self.data['mV1'] = 42.0*mV
        self.data['ampere1'] = 1*mA
        self.data['integer'] = 16
        #self.data['kHz05'] = 0.5*kHz
        self.data['nested_array'] = np.array([[6.,7.,8.],[9.,10.,11.]]) * ms
        self.data['b2a'] = np.array([1., 2.]) * mV
        self.data['complex'] = np.array([1., 2.]) * mV*mV/mA**2.73

        super(Brian2ParameterTest, self).setUp()
        self.dynamic_imports = [Brian2Parameter]

    def make_params(self):
        self.param = {}
        for key, val in self.data.items():
            self.param[key] = Brian2Parameter(self.location+'.'+key, val, comment=key)

    def explore(self):
        self.explore_dict = cartesian_product({
                                            #'npstr': [np.array(['Uno', 'Dos', 'Tres']),
                                            #           np.array(['Cinco', 'Seis', 'Siette']),
                                            #           np.array(['Ocho', 'Nueve', 'Diez'])],
                                            'ampere1': [1*mA],
                                             #'val0': [1, 2, 3],
                                             'mV1': [42.0*mV, 3*mV, 4*mV],
                                             'b2a': [np.array([1., 2.]) * mV]})

        ## Explore the parameter:
        for key, vallist in self.explore_dict.items():
            self.param[key]._explore(vallist)
            self.assertTrue(self.param[key].v_explored and self.param[key].f_has_range())

    def test_supports(self):
        for key, val in self.data.items():
            self.assertTrue(self.param[key].f_supports(val))


    def test_false_on_values_not_of_same_type(self):
        self.assertFalse(self.param[list(self.param.keys())[0]]._values_of_same_type(11, 99*mV))


@unittest.skipIf(brian2 is None, 'Can only be run with brian2!')
class Brian2ParameterDuplicatesInStoreTest(unittest.TestCase):

    tags = 'unittest', 'brian2', 'parameter', 'store', 'henri'

    def setUp(self):
        self.data = {}
        self.data['brian2_single_a'] = 1. * mV
        self.data['brian2_array_b'] = np.array([3., 3., 4.]) * mV
        self.data['brian2_array_c'] = np.array([5.]) * mV
        self.data['brian2_array_d'] = np.array([[6.,7.,8.],[9.,10.,11.]]) * ms
        #self.data['brian2_mixedtype_array_a'] = np.array([9., 10.]) * mV
        self.data['brian2_mixedtype_array_b'] = np.array([13., 14.]) * mV

        self.location = 'MyName.Is.myParam'
        self.make_params()
        self.explore()

    def make_params(self):
        self.param = {}
        for key, val in self.data.items():
            self.param[key] = Brian2Parameter(self.location+'.'+key, val, comment=key)

    def explore(self):
        self.explore_dict = cartesian_product({#'brian2_array_a': [np.array([1., 2.]) * mV],
                                               # 'brian2_array_b': [2 * mV],
                                               # Arrays need to be of the same size!
                                               'brian2_array_c': [np.array([5., 8.]) * mV, np.array([7., 8.]) * mV],
                                               })


        ## Explore the parameter:
        for key, vallist in self.explore_dict.items():
            self.param[key]._explore(vallist)
            self.assertTrue(self.param[key].v_explored and self.param[key].f_has_range())


    def test_storage_and_loading(self):
        for key, param in self.param.items():
            store_dict = param._store()

            # Due to smart storing the storage dict should be small and only contain 5 items or less
            # 1 for data, 1 for reference, and 3 for the array/matrices/items
            if param.f_has_range():
                if isinstance(param,(ArrayParameter, PickleParameter)) and not isinstance(param, SparseParameter):
                    self.assertTrue(len(store_dict)<7)
                # For sparse parameter it is more:
                if isinstance(param, SparseParameter):
                    self.assertTrue(len(store_dict)<23)

            constructor = param.__class__

            param.f_unlock()
            param.f_empty()

            param = constructor('')

            param._load(store_dict)

            param._rename(self.location+'.'+key)

            self.param[key] = param

        self.test_the_insertion_made_implicetly_in_setUp()

        self.test_exploration()

        self.test_meta_settings()


    def test_the_insertion_made_implicetly_in_setUp(self):
        for key, val in self.data.items():
            if not key in self.explore_dict:
                self.param[key]._restore_default()
                param_val = self.param[key].f_get()
                self.assertTrue(np.all(repr(val) == repr(param_val)),'%s != %s'  %(str(val),str(param_val)))

    def test_exploration(self):
        for key, vallist in self.explore_dict.items():
            param = self.param[key]

            for idx, val in enumerate(vallist):
                assert isinstance(param, BaseParameter)
                param._set_parameter_access(idx)

                self.assertTrue(np.all(repr(param.f_get())==repr(val))),'%s != %s'%( str(param.f_get()),str(val))

                param_val = self.param[key].f_get_range()[idx]
                self.assertTrue(np.all(str(val) == str(param_val)),'%s != %s'  %(str(val),str(param_val)))

            param._restore_default()
            self.assertTrue(param.v_explored and param.f_has_range(), 'Error for %s' % key)
            val = self.data[key]
            self.assertTrue(np.all(repr(param.f_get())==repr(val))),'%s != %s'%( str(param.f_get()),str(val))

    def test_expanding(self):
        for key, vallist in self.explore_dict.items():
            param = self.param[key]

            copy_list = vallist.copy()
            old_len = len(vallist)

            param.f_unlock()
            param._expand(copy_list)

            new_len = len(param.f_get_range())

            self.assertEqual(new_len, 2 * old_len)

    def test_loading_and_expanding(self):
        # Regression test for issue #50
        # https://github.com/SmokinCaterpillar/pypet/issues/50
        for key, vallist in self.explore_dict.items():
            param = self.param[key]

            copy_list = vallist.copy()
            old_len = len(vallist)


            store_dict = param._store()
            param.f_unlock()
            param._load(store_dict)

            param.f_unlock()
            param._expand(copy_list)

            new_len = len(param.f_get_range())

            self.assertEqual(new_len, 2 * old_len)

    def test_meta_settings(self):
        for key, param in self.param.items():
            self.assertEqual(param.v_full_name, self.location+'.'+key)
            self.assertEqual(param.v_name, key)
            self.assertEqual(param.v_location, self.location)


@unittest.skipIf(brian2 is None, 'Can only be run with brian2!')
class Brian2ResultTest(ResultTest):

    tags = 'unittest', 'brian2', 'result', 'henri'

    def make_constructor(self):
        self.Constructor = Brian2Result
        self.dynamic_imports = [Brian2Result]

    def test_illegal_naming(self):
        for res in self.results.values():
            data_dict = {'val'+Brian2Result.IDENTIFIER:42}
            with self.assertRaises(AttributeError):
                res.f_set(**data_dict)


    def setUp(self):

        if not hasattr(self,'data'):
            self.data = {}

        self.data['mV1'] = 1*mV
        self.data['ampere1'] = 1*mA
        self.data['msecond17'] = 16*ms
        self.data['kHz05'] = 0.5*kHz

        self.data['mV_array'] = np.ones(20) * mV
        self.data['integer'] = 444
        self.data['complex'] = np.array([1., 2.]) * mV*mV/mA**-2.7343

        super(Brian2ResultTest, self).setUp()


@unittest.skipIf(brian2 is None, 'Can only be run with brian2!')
class Brian2GetUnitFastTest(unittest.TestCase):

    tags = 'unittest', 'brian2'

    def test_get_unit_fast(self):
        unit = get_unit_fast(42 * mV)
        self.assertEquals(unit, 1000 * mV)


if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)
