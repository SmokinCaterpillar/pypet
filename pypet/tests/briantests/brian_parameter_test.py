__author__ = 'Robert Meyer'

import sys

import numpy as np
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

from pypet.brian.parameter import BrianParameter, BrianResult
from pypet.tests.parameter_test import ParameterTest, ResultTest
from brian.stdunits import mV, mA, kHz,ms
from pypet.utils.explore import cartesian_product




class BrianParameterTest(ParameterTest):

    def setUp(self):

        if not hasattr(self,'data'):
            self.data = {}

        self.data['mV1'] = 1*mV
        self.data['ampere1'] = 1*mA
        self.data['msecond17'] = 16*ms
        self.data['kHz05'] = 0.5*kHz

        super(BrianParameterTest,self).setUp()


    def make_params(self):
        self.param = {}
        for key, val in self.data.items():
            self.param[key] = BrianParameter(self.location+'.'+key, val, comment=key)



    def explore(self):
        self.explore_dict=cartesian_product({'npstr':[np.array(['Uno', 'Dos', 'Tres']),
                               np.array(['Cinco', 'Seis', 'Siette']),
                            np.array(['Ocho', 'Nueve', 'Diez'])],
                           'val0':[1,2,3],
                           'mV1' : [42.0*mV,3*mV,4*mV]})




        ## Explore the parameter:
        for key, vallist in self.explore_dict.items():
            self.param[key]._explore(vallist)
            self.assertTrue(self.param[key].v_explored and self.param[key].f_has_range())


class BrianParameterStringModeTest(BrianParameterTest):

    def make_params(self):
        self.param = {}
        for key, val in self.data.items():
            self.param[key] = BrianParameter(self.location+'.'+key, val, comment=key)
            self.param[key].v_storage_mode = BrianParameter.STRING_MODE


class BrianResultTest(ResultTest):

    def make_constructor(self):
        self.Constructor=BrianResult

    def test_illegal_naming(self):
        for res in self.results.values():
            data_dict = {'val'+BrianResult.IDENTIFIER:42}
            with self.assertRaises(AttributeError):
                res.f_set(**data_dict)


    def setUp(self):

        if not hasattr(self,'data'):
            self.data = {}

        self.data['mV1'] = 1*mV
        self.data['ampere1'] = 1*mA
        self.data['msecond17'] = 16*ms
        self.data['kHz05'] = 0.5*kHz

        super(BrianResultTest, self).setUp()


class BrianResultStringModeTest(BrianResultTest):

    def setUp(self):
        super(BrianResultStringModeTest, self).setUp()

        for res in self.results.values():
            res.v_storage_mode=BrianResult.STRING_MODE


if __name__ == '__main__':
    unittest.main()
     #cProfile.run('unittest.main()',sort=0)

