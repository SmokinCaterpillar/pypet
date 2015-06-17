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

    '''
    def __init__(self, other):
        self.data = {}
        super(Brian2ParameterTest,self).__init__()
    '''

    def setUp(self):

        if not hasattr(self,'data'):
            self.data = {}

        self.data['mV1'] = [42.0*mV, 3*mV, 4*mV]
        self.data['ampere1'] = [1*mA]
        #self.data['msecond17'] = 16*ms
        #self.data['kHz05'] = 0.5*kHz
        self.data['b2a'] = [np.array([1., 2.]) * mV]

        super(Brian2ParameterTest, self).setUp()


    def make_params(self):
        self.param = {}
        for key, val in self.data.items():
            self.param[key] = Brian2Parameter(self.location+'.'+key, val, comment=key)



    def explore(self):
        self.explore_dict=cartesian_product({
                                            #'npstr': [np.array(['Uno', 'Dos', 'Tres']),
                                            #           np.array(['Cinco', 'Seis', 'Siette']),
                                            #           np.array(['Ocho', 'Nueve', 'Diez'])],
                                            'ampere1': [1*mA],
                                             #'val0': [1, 2, 3],
                                             'mV1': [42.0*mV, 3*mV, 4*mV],
                                             'b2a': [np.array([1., 2.]) * mV]})
        print("explore self.explore_dict:"+str(self.explore_dict))




        ## Explore the parameter:
        for key, vallist in self.explore_dict.items():
            self.param[key]._explore(vallist)
            self.assertTrue(self.param[key].v_explored and self.param[key].f_has_range())

        print("explore self.param:"+str(self.param))

    pass

class Brian2ParameterSupportsTest(Brian2ParameterTest):

    tags = 'unittest', 'brian2', 'parameter', 'supports', 'henri'

    def make_params(self):
        self.param = {}
        print("Brian2ParameterSupportsTest self.data.items:"+str(self.data.items()))
        for key, val in self.data.items():
            self.param[key] = Brian2Parameter(self.location+'.'+key, val, comment=key)

class Brian2ParameterDuplicatesInStoreTest(unittest.TestCase):

    tags = 'unittest', 'brian2', 'parameter', 'store', 'henri'

    def setUp(self):
        self.data = {}
        #self.data['brian2_array_a'] = np.array([1., 2.]) * mV
        #self.data['brian2_array_b'] = [np.array([3., 3., 4.]) * mV]
        self.data['brian2_array_c'] = [np.array([5.]) * mV, np.array([7., 8.]) * mV]
        #self.data['brian2_mixedtype_array_a'] = [np.array([9., 10.]) * mV, np.array([11., 12.]) * ms]
        #self.data['brian2_mixedtype_array_b'] = [np.array([13., 14.]) * mV, 15. * mV]

        self.location = 'MyName.Is.myParam'
        self.make_params()
        self.explore()

    def make_params(self):
        self.param = {}
        for key, val in self.data.items():
            self.param[key] = Brian2Parameter(self.location+'.'+key, val, comment=key)
        print("make_params param", self.param)

    def explore(self):
        print("~~~ Brian2ParameterDuplicatesInStoreTest explore START ~~~")
        import itertools
        # for element in itertools.product([np.array([1., 2.]) * mV, np.array([3., 4.]) * mV]):
        #    print element
        self.explore_dict = cartesian_product({#'brian2_array_a': [np.array([1., 2.]) * mV],
                                               #'brian2_array_b': [np.array([3., 3., 4.]) * mV],
                                               'brian2_array_c': [np.array([5.]) * mV, np.array([7., 8.]) * mV],
                                               #'brian2_mixedtype_array_a': [np.array([9., 10.]) * mV, np.array([11., 12.]) * ms],
                                               #'brian2_mixedtype_array_b': [np.array([13., 14.]) * mV, 15. * mV],
                                               })
        print("explore explore_dict",self.explore_dict)


        ## Explore the parameter:
        print("explore 1 param", self.param)
        for key, vallist in self.explore_dict.items():
            print("explore self.param", self.param, "key", key)
            print("explore param", self.param[key], "_data", self.param[key]._data)
            self.param[key]._explore(vallist)
            self.assertTrue(self.param[key].v_explored and self.param[key].f_has_range())
        print("explore 2 param", self.param)

        print("~~~ Brian2ParameterDuplicatesInStoreTest explore END ~~~")


    def test_storage_and_loading(self):
        print("~~~Brian2ParameterDuplicatesInStoreTest test_storage_and_loading~~~")

        print("test_storage_and_loading 1 param", self.param)
        for key, param in self.param.items():
            print("--- tsl key " + str(key) + " ---")
            print("test_storage_and_loading 2 self.param", self.param)
            print("test_storage_and_loading 2 param", param)
            store_dict = param._store()

            print("key", key, "param", param," self.explore_dict", self.explore_dict.items())
            print("test_storage_and_loading 3 param", self.param)

            # Due to smart storing the storage dict should be small and only contain 5 items or less
            # 1 for data, 1 for reference, and 3 for the array/matrices/items
            if param.f_has_range():
                if isinstance(param,(ArrayParameter, PickleParameter)) and not isinstance(param, SparseParameter):
                    self.assertTrue(len(store_dict)<7)
                # For sparse parameter it is more:
                if isinstance(param, SparseParameter):
                    self.assertTrue(len(store_dict)<23)

            print("test_storage_and_loading 4 param", self.param)

            print("test_storage_and_loading explore_dict:"+str(self.explore_dict))
            constructor = param.__class__
            print("test_storage_and_loading 5 about to empty param", self.param)

            param.f_unlock()
            param.f_empty()

            print("test_storage_and_loading 6 param", self.param)
            param = constructor('')

            print("test_storage_and_loading 7 param", self.param, "store_dict", store_dict)
            param._load(store_dict)

            print("test_storage_and_loading 8 param", self.param)
            param._rename(self.location+'.'+key)

            print("test_storage_and_loading 9 param", self.param)
            self.param[key] = param
            print("test_storage_and_loading 10 param", self.param)


        print("test_storage_and_loading 11 param", self.param)
        self.test_the_insertion_made_implicetly_in_setUp()

        print("test_storage_and_loading 12 param", self.param)
        print("test_storage_and_loading 13 self.explore_dict",self.explore_dict.items())

        self.test_exploration()
        print("test_storage_and_loading 14 self.explore_dict",self.explore_dict.items())

        self.test_meta_settings()
        print("test_storage_and_loading 15 self.explore_dict",self.explore_dict.items())


    def test_the_insertion_made_implicetly_in_setUp(self):
        for key, val in self.data.items():

            print("test_the_insertion_made_implicetly_in_setUp 1 param", self.param)
            if not key in self.explore_dict:
                self.param[key]._restore_default()
                param_val = self.param[key].f_get()
                self.assertTrue(np.all(repr(val) == repr(param_val)),'%s != %s'  %(str(val),str(param_val)))
            print("test_the_insertion_made_implicetly_in_setUp 2 param", self.param)

    def test_exploration(self):
        print("test_exploration 1 self.explore_dict",self.explore_dict.items())
        print("test_exploration 1  param", self.param)
        for key, vallist in self.explore_dict.items():

            print("test_exploration 2 self.param", self.param, "key", key, "vallist", vallist)

            param = self.param[key]

            print("test_exploration 3 param", param, "_data", param._data)

            for idx, val in enumerate(vallist):
                assert isinstance(param, BaseParameter)
                print("test_exploration 4 val",val, "param._data", param._data)
                param._set_parameter_access(idx)

                print("test_exploration 5 val",val, "param._data", param._data)
                #param.f_get() === b2p.self._data
                self.assertTrue(np.all(repr(param.f_get())==repr(val))),'%s != %s'%( str(param.f_get()),str(val))

                param_val = self.param[key].f_get_range()[idx]
                self.assertTrue(np.all(str(val) == str(param_val)),'%s != %s'  %(str(val),str(param_val)))

            param._restore_default()
            self.assertTrue(param.v_explored and param.f_has_range(), 'Error for %s' % key)
            val = self.data[key]
            print("test_exploration 6 param._data",param._data," == val",val)
            print("test_exploration 6 param:",param)
            self.assertTrue(np.all(repr(param.f_get())==repr(val))),'%s != %s'%( str(param.f_get()),str(val))

    def test_meta_settings(self):
        print("test_meta_settings param", self.param)
        for key, param in self.param.items():
            self.assertEqual(param.v_full_name, self.location+'.'+key)
            self.assertEqual(param.v_name, key)
            self.assertEqual(param.v_location, self.location)





if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)
