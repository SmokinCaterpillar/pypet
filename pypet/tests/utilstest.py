from pypet.utils.comparisons import nested_equal

__author__ = 'Robert Meyer'


import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

from pypet.utils.explore import cartesian_product


class CartesianTest(unittest.TestCase):

    def test_cartesian_product(self):

        cartesian_dict=cartesian_product({'param1':[1,2,3], 'param2':[42.0, 52.5]},
                                          ('param1','param2'))
        result_dict = {'param1':[1,1,2,2,3,3],'param2': [42.0,52.5,42.0,52.5,42.0,52.5]}

        self.assertTrue(nested_equal(cartesian_dict,result_dict), '%s != %s' %
                                                        (str(cartesian_dict),str(result_dict)))

    def test_cartesian_product_combined_params(self):
        cartesian_dict=cartesian_product( {'param1': [42.0, 52.5], 'param2':['a', 'b'],\
            'param3' : [1,2,3]}, (('param3',),('param1', 'param2')))

        result_dict={'param3':[1,1,2,2,3,3],'param1' : [42.0,52.5,42.0,52.5,42.0,52.5],
                      'param2':['a','b','a','b','a','b']}

        self.assertTrue(nested_equal(cartesian_dict,result_dict), '%s != %s' %
                                                    (str(cartesian_dict),str(result_dict)))



if __name__ == '__main__':
    unittest.main()