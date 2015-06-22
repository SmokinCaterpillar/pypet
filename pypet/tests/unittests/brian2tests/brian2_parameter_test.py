__author__ = 'Henri Bunting'

import sys

import numpy as np
from pypet.parameter import BaseParameter

if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

from pypet.parameter import PickleParameter, ArrayParameter, SparseParameter
from brian2.units.stdunits import mV, mA, kHz, ms
from pypet.tests.unittests.parameter_test import ParameterTest, ResultTest
from pypet.tests.testutils.ioutils import parse_args, run_suite
from pypet.brian2.parameter import Brian2Parameter
from pypet.utils.explore import cartesian_product

import logging
logging.basicConfig(level=logging.DEBUG)


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

        super(Brian2ParameterTest, self).setUp()

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
        for key, val in self.explore_dict.items():
            self.assertTrue(self.param[key].f_supports(val))

    def test_values_of_same_type(self):
        self.param[self.explore_dict.items()[0][0]]._values_of_same_type(11, 99*mV)


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
                                               'brian2_array_b': [np.array([3., 3., 4.]) * mV],
                                               'brian2_array_c': [np.array([5.]) * mV, np.array([7., 8.]) * mV],
                                               #'brian2_mixedtype_array_a': [np.array([9., 10.]) * mV, np.array([11., 12.]) * ms],
                                               'brian2_mixedtype_array_b': [np.array([13., 14.]) * mV, 15. * mV],
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

    def test_meta_settings(self):
        for key, param in self.param.items():
            self.assertEqual(param.v_full_name, self.location+'.'+key)
            self.assertEqual(param.v_name, key)
            self.assertEqual(param.v_location, self.location)





if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)
