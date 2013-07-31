import mypet

__author__ = 'robert'


import numpy as np
import unittest
from mypet.parameter import Parameter

class ParameterTest(unittest.TestCase):



    def testParameterCreation(self):
        fullname = 'MyName.Is.myParam'
        split_name = fullname.split('.')
        name = split_name.pop()
        location = '.'.join(split_name)

        myParam = Parameter(fullname)

        self.assertEqual(myParam.get_fullname(), fullname)
        self.assertEqual(myParam.get_name(), name)
        self.assertEqual(myParam.get_location(), location)


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

        self.param = Parameter('MyName.Is.myParam', self.val0,self.val1,self.val2,self.val3,
                               npfloat=self.npfloat,
                               npfloat_2d=self.npfloat_2d,
                               npbool=self.npbool,
                               npstr=self.npstr,
                               npint=self.npint)

    def test_the_insertion_made_implicetly_in_setUp(self):
        self.assertEqual(self.param.val,self.val0)
        self.assertEqual(self.param.val0,self.val0)
        self.assertEqual(self.param.get('val0'),self.val0)
        self.assertEqual(self.param.get('val1'),self.val1)
        self.assertEqual(self.param.get('val2'),self.val2)
        self.assertEqual(self.param.get('val3'),self.val3)










if __name__ == '__main__':
    unittest.main()
