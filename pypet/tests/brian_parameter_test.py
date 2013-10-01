__author__ = 'Robert Meyer'


import numpy as np
import unittest
from pypet.brian.parameter import BrianParameter
from pypet.tests.parameter_test import ParameterTest, Dummy
from brian.stdunits import mV, mA, kHz,ms


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
        self.explore_dict={'npstr':[np.array(['Uno', 'Dos', 'Tres']),
                               np.array(['Cinco', 'Seis', 'Siette']),
                            np.array(['Ocho', 'Nueve', 'Diez'])],
                           'val0':[1,2,3],
                           'mV1' : [42.0*mV,3*mV,4*mV]}




        ## Explore the parameter:
        for key, vallist in self.explore_dict.items():
            self.param[key]._explore(vallist)


if __name__ == '__main__':
    unittest.main()
     #cProfile.run('unittest.main()',sort=0)

