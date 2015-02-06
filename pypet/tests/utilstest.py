

__author__ = 'Robert Meyer'

import time
import logging
import pandas as pd
import numpy as np

from pypet.tests.test_helpers import add_params, create_param_dict, simple_calculations, make_run,\
    make_temp_file, TrajectoryComparator, multiply, make_trajectory_name, remove_data

from pypet.trajectory import Trajectory
from pypet.parameter import ArrayParameter, Parameter

import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

from pypet.utils.explore import cartesian_product, find_unique_points
from pypet.utils.helpful_functions import progressbar, nest_dictionary, flatten_dictionary
from pypet.utils.comparisons import nested_equal
from pypet.utils.to_new_tree import FileUpdater
import pypet.compat as compat



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


@unittest.skipIf(sys.version_info < (2, 7, 0), 'progressbar does not work under python 2.6')
class ProgressBarTest(unittest.TestCase):

    def test_progressbar(self):

        total = 55
        percentage_step = 17

        for irun in range(total):
            time.sleep(0.005)
            progressbar(irun, total, percentage_step)

    def test_progressbar_w_wo_time(self):

        total = 55
        percentage_step = 17

        shows_time = False
        for irun in range(total):
            time.sleep(0.005)
            s = progressbar(irun, total, percentage_step, time=True)
            if s and 'remaining' in s:
               shows_time = True

        self.assertTrue(shows_time)

        shows_time = False
        for irun in range(total):
            time.sleep(0.005)
            s = progressbar(irun, total, percentage_step, time=False)
            if s and 'remaining' in s:
                shows_time = True

        self.assertFalse(shows_time)

    def test_progressbar_resume(self):

        total = 55

        for irun in range(total):
            time.sleep(0.005)
            progressbar(irun, total, 5)

        for irun in range(2*total):
            time.sleep(0.005)
            progressbar(irun, 2*total, 10)


    def test_progressbar_float(self):

        total = 55

        for irun in range(total):
            time.sleep(0.005)
            progressbar(irun, total, 5.1)

        for irun in range(2*total):
            time.sleep(0.005)
            progressbar(irun, 2*total, 0.5)

    def test_progressbar_logging(self):
        logger = logging.getLogger()

        total = 22

        for irun in range(total):
            time.sleep(0.005)
            progressbar(irun, total, logger=logger)

class TestFindUnique(unittest.TestCase):

    def test_find_unique(self):
        paramA = Parameter('ggg', 33)
        paramA._explore([1, 2, 1, 2, 1, 2])
        paramB = Parameter('hhh', 'a')
        paramB._explore(['a', 'a', 'a', 'a', 'b', 'b'])
        unique_elements = find_unique_points([paramA, paramB])
        self.assertTrue(len(unique_elements) == 4)
        self.assertTrue(len(unique_elements[1][1]) == 2)
        self.assertTrue(len(unique_elements[3][1]) == 1)

        paramC = ArrayParameter('jjj', np.zeros((3,3)))
        paramC._explore([np.ones((3,3)),
                         np.ones((3,3)),
                         np.ones(499),
                         np.ones((3,3)),
                         np.zeros((3,3,3)),
                         np.ones(1)])
        unique_elements = find_unique_points([paramA, paramC])
        self.assertTrue(len(unique_elements) == 5)
        self.assertTrue(len(unique_elements[1][1]) == 2)
        self.assertTrue(len(unique_elements[0][1]) == 1)

        unique_elements = find_unique_points([paramC, paramB])
        self.assertTrue((len(unique_elements))==4)
        self.assertTrue(len(unique_elements[0][1])==3)
        self.assertTrue(len(unique_elements[3][1])==1)


class TestDictionaryMethods(unittest.TestCase):

    def test_nest_dicitionary(self):
        mydict = {'a.b.c' : 4, 'a.c' : 5, 'd':4}
        nested = nest_dictionary(mydict, separator='.')
        expected = {'a':{'b':{'c':4}, 'c':5}, 'd':4}
        self.assertTrue(expected == nested)

    def test_flatten_dictionary(self):
        mydict = {'a':{'b':{'c':4}, 'c':5}, 'd':4}
        flattened = flatten_dictionary(mydict, separator='.')
        expected = {'a.b.c' : 4, 'a.c' : 5, 'd':4}
        self.assertTrue(flattened == expected)


@unittest.skipIf(compat.python >= 3, 'Only supported for python 2')
class TestNewTreeTranslation(unittest.TestCase):

    def test_file_translation(self):
        filename = make_temp_file('to_new_tree.hdf5')
        mytraj = Trajectory('SCRATCH', filename=filename)

        mytraj.f_add_parameter('Test.Group.Test', 42)

        mytraj.f_add_derived_parameter('trajectory.saaaa',33)

        mytraj.f_add_derived_parameter('trajectory.intraj.dpar1',33)

        mytraj.f_add_derived_parameter('run_00000008.inrun.dpar2',33)
        mytraj.f_add_derived_parameter('run_00000001.inrun.dpar3',35)


        mytraj.f_add_result('trajectory.intraj.res1',33)

        mytraj.f_add_result('run_00000008.inrun.res1',33)

        mytraj.f_store()

        mytraj.f_migrate(new_name=mytraj.v_name + 'PETER', in_store=True)

        mytraj.f_store()

        fu=FileUpdater(filename=filename, backup=True)

        fu.update_file()

        mytraj = Trajectory(name=mytraj.v_name, add_time=False, filename=filename)
        mytraj.f_load(load_parameters=2, load_derived_parameters=2, load_results=2)

        for node in mytraj.f_iter_nodes():
            self.assertTrue(node.v_name != 'trajectory')

            if 'run_' in node.v_full_name:
                self.assertTrue('.runs.' in node.v_full_name)

        remove_data()


class MyDummy(object):
    pass


class TestEqualityOperations(unittest.TestCase):

    def test_nested_equal(self):
        self.assertTrue(nested_equal(4, 4))
        self.assertFalse(nested_equal(4, 5))

        frameA = pd.DataFrame(data={'a':[np.zeros((19,19))]}, dtype=object)
        frameB = pd.DataFrame(data={'a':[np.zeros((19,19))]}, dtype=object)

        self.assertTrue(nested_equal(frameA, frameB))

        frameB.loc[0,'a'][0,0] = 3
        self.assertFalse(nested_equal(frameA, frameB))

        seriesA = pd.Series(data=[[np.zeros((19,19))]], dtype=object)
        seriesB = pd.Series(data=[[np.zeros((19,19))]], dtype=object)

        self.assertTrue(nested_equal(seriesA, seriesB))

        seriesA.loc[0] = 777
        self.assertFalse(nested_equal(seriesA, seriesB))

        a = MyDummy()
        a.g = 4
        b = MyDummy()
        b.g = 4

        self.assertTrue(nested_equal(a, b))

        a.h = [1, 2, 42]
        b.h = [1, 2, 43]

        self.assertFalse(nested_equal(a, b))


if __name__ == '__main__':
    make_run()



