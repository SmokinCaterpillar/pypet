__author__ = 'robert'


import numpy as np
import unittest
from mypet.parameter import ParameterSet, SparseParameter
from mypet.brian.parameter import BrianParameter
import pickle
import scipy.sparse as spsp
from mypet.tests.parameter_test import SparseParameterTest

from brian.stdunits import *


class BrianParameterTest(SparseParameterTest):

    def setUp(self):
        self.val0 = 1
        self.val1 = 1.0
        self.val2 = True
        self.val3 = 'String'
        self.npfloat = np.array([1.0,2.0,3.0])
        self.npfloat_2d = np.array([[1.0,2.0],[3.0,4.0]])
        self.npbool= np.array([True,False, True])
        self.npstr = np.array(['Uno', 'Dos', 'Tres'])
        self.npint = np.array([1,2,3])
        self.spsparse_csc = spsp.csc_matrix((1000,100))
        self.spsparse_csc[1,2] = 44.5

        self.spsparse_csr = spsp.csr_matrix((2222,22))
        self.spsparse_csr[1,3] = 44.5

        self.spsparse_lil = spsp.lil_matrix((111,111))
        self.spsparse_lil[3,2] = 44.5

        self.fullname = 'MyName.Is.myParam'
        self.split_name = self.fullname.split('.')
        self.name = self.split_name.pop()
        self.location = '.'.join(self.split_name)

        self.mV = 222.0*mV
        self.ampere = 2.0*mA
        self.second = 22 * ms/mm2

        self.param = BrianParameter(self.fullname, self.val0,self.val1,self.val2,self.val3,
                               npfloat=self.npfloat,
                               npfloat_2d=self.npfloat_2d,
                               npbool=self.npbool,
                               npstr=self.npstr,
                               npint=self.npint)

        self.param.set(spsparse_csc=self.spsparse_csc)
        self.param.set(spsparse_csr=self.spsparse_csr)
        self.param.set(spsparse_lil=self.spsparse_lil)

        self.param.set(mV=self.mV, ampere=self.ampere, second= self.second)

        with self.assertRaises(AttributeError):
            self.param.set([[1,2,3],[1,2,3]])

        with self.assertRaises(AttributeError):
            self.param.set(spsp.coo_matrix((12,12)))

        #Add explortation:
        self.explore_dict={'npstr':[np.array(['Uno', 'Dos', 'Tres']),
                               np.array(['Cinco', 'Seis', 'Siette']),
                            np.array(['Ocho', 'Nueve', 'Diez'])]}

        ## Explore the parameter:
        self.param.explore(self.explore_dict)



    def test_the_insertion_made_implicetly_in_setUp(self):
        super(BrianParameterTest,self).test_the_insertion_made_implicetly_in_setUp()


        self.assertTrue(self.param.mV == self.mV)
        self.assertTrue(self.param.second == self.second)
        self.assertTrue(self.param.ampere == self.ampere)



if __name__ == '__main__':
    unittest.main()


