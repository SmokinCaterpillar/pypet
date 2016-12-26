__author__ = 'Robert Meyer'

import time
import sys
import pickle
from collections import Set, Sequence, Mapping

import pandas as pd
import numpy as np
import random
import copy as cp

from pypet.tests.testutils.ioutils import run_suite, make_temp_dir, remove_data, \
    get_root_logger, parse_args
from pypet.trajectory import Trajectory
from pypet.parameter import ArrayParameter, Parameter, SparseParameter, PickleParameter

import unittest

from pypet.utils.explore import cartesian_product, find_unique_points
from pypet.utils.helpful_functions import progressbar, nest_dictionary, flatten_dictionary, \
    result_sort, get_matching_kwargs
from pypet.utils.comparisons import nested_equal
from pypet.utils.helpful_classes import IteratorChain
from pypet.utils.decorators import retry
from pypet import HasSlots


class RaisesNTypeErrors(object):

    def __init__(self, n):
        self.__name__ = RaisesNTypeErrors.__name__
        self.n = n
        self.retries = 0

    def __call__(self):
        if self.retries < self.n:
            self.retries += 1
            raise TypeError('Nope!')


class RetryTest(unittest.TestCase):

    tags = 'unittest', 'utils', 'retry'

    def test_fail_after_n_tries(self):
        x = RaisesNTypeErrors(5)
        x = retry(4, TypeError, 0.01, 'ERROR')(x)
        with self.assertRaises(TypeError):
            x()

    def test_succeeds_after_retries(self):
        x = RaisesNTypeErrors(5)
        x = retry(5, TypeError, 0.01, 'ERROR')(x)
        x()


class CartesianTest(unittest.TestCase):

    tags = 'unittest', 'utils', 'cartesian_product'

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


class ProgressBarTest(unittest.TestCase):

    tags = 'unittest', 'utils', 'progress_bar'

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
        logger = get_root_logger()

        total = 33

        for irun in range(total):
            time.sleep(0.005)
            progressbar(irun, total, logger=logger)

        for irun in range(total):
            time.sleep(0.005)
            progressbar(irun, total, logger='GetLogger')

class TestFindUnique(unittest.TestCase):

    tags = 'unittest', 'utils', 'find_unique'

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

    tags = 'unittest', 'utils'

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


class ResultSortFuncTest(unittest.TestCase):
    tags = 'unittest', 'utils', 'result_sort'

    def result_sort_sorted(the_list, start_index=0):
        to_sort = the_list[start_index:]
        sorted_list = sorted(to_sort, key=lambda key: key[0])
        for idx_count, elem in enumerate(sorted_list):
            the_list[idx_count+start_index] = elem
        return the_list

    def test_sort(self, start_index=0, n=100):
        to_sort = list(range(n)) # list for Python 3
        random.shuffle(to_sort)
        to_sort = [(x,x) for x in to_sort]
        result_sort(to_sort, start_index)
        if start_index == 0:
            compare = [(x,x,) for x in range(n)]
        else:
            copy_to_sort = cp.deepcopy(to_sort)
            compare = result_sort(copy_to_sort, start_index)
        self.assertEqual(to_sort, compare)
        if start_index != 0:
            self.assertNotEqual(to_sort[:start_index], [(x,x,) for x in range(n)][:start_index])

    def test_sort_with_index(self):
        self.test_sort(500, 1000)


class MyDummy(object):
    pass

class MyDummyWithSlots(object):
    __slots__ = ('a', 'b')

class MyDummyWithSlots2(HasSlots):
    __slots__ = ('a', 'b')

class MyDummyCMP(object):
    def __init__(self, data):
        self.data = data

    def __cmp__(self, other):
        if self.data == other.data:
            return 0
        elif self.data < other.data:
            return -1
        else:
            return 1

class MyDummySet(Set):
    def __init__(self, *args, **kwargs):
        self._set = set(*args, **kwargs)

    def __getattr__(self, item):
        return getattr(self._set, item)

    def __contains__(self, item):
        return self._set.__contains__(item)

    def __len__(self):
        return self._set.__len__()

    def __iter__(self):
        return self._set.__iter__()

class MyDummyList(Sequence):
    def __init__(self, *args, **kwargs):
        self._list = list(*args, **kwargs)

    def __len__(self):
        return self._list.__len__()

    def __getitem__(self, item):
        return self._list.__getitem__(item)

    def append(self, item):
        return self._list.append(item)

class MyDummyMapping(Mapping):
    def __init__(self, *args, **kwargs):
        self._dict = dict(*args, **kwargs)

    def __getitem__(self, item):
        return self._dict.__getitem__(item)

    def __iter__(self):
        return self._dict.__iter__()

    def __len__(self):
        return self._dict.__len__()

class TestEqualityOperations(unittest.TestCase):

    tags = 'unittest', 'utils', 'equality'

    def test_nested_equal(self):
        self.assertTrue(nested_equal(4, 4))
        self.assertFalse(nested_equal(4, 5))
        self.assertFalse(nested_equal(5, 4))

        self.assertTrue(nested_equal(4, np.int8(4)))
        self.assertTrue(nested_equal(np.int8(4), 4))

        self.assertFalse(nested_equal(4, np.int8(5)))

        self.assertFalse(nested_equal( np.int8(5), 4))

        frameA = pd.DataFrame(data={'a':[np.zeros((19,19))]}, dtype=object)
        frameB = pd.DataFrame(data={'a':[np.zeros((19,19))]}, dtype=object)

        self.assertTrue(nested_equal(frameA, frameB))
        self.assertTrue(nested_equal(frameB, frameA))

        frameB.loc[0,'a'][0,0] = 3
        self.assertFalse(nested_equal(frameA, frameB))
        self.assertFalse(nested_equal(frameB, frameA))

        seriesA = pd.Series(data=[[np.zeros((19,19))]], dtype=object)
        seriesB = pd.Series(data=[[np.zeros((19,19))]], dtype=object)

        self.assertTrue(nested_equal(seriesA, seriesB))

        self.assertTrue(nested_equal(seriesB, seriesA))

        seriesA.loc[0] = 777
        self.assertFalse(nested_equal(seriesA, seriesB))

        self.assertFalse(nested_equal(seriesB, seriesA))


        seriesA = pd.Series([1,2,3])
        seriesB = pd.Series([1,2,3])

        self.assertTrue(nested_equal(seriesA, seriesB))

        self.assertTrue(nested_equal(seriesB, seriesA))

        a = MyDummy()
        a.g = 4
        b = MyDummy()
        b.g = 4

        self.assertTrue(nested_equal(a, b))
        self.assertTrue(nested_equal(b, a))


        a.h = [1, 2, 42]
        b.h = [1, 2, 43]

        self.assertFalse(nested_equal(a, b))
        self.assertFalse(nested_equal(b, a))

        a = MyDummyWithSlots()
        a.a = 1
        a.b = 2
        b = MyDummyWithSlots2()
        b.a = 1
        b.b = 2

        self.assertTrue(nested_equal(a, b))

        self.assertTrue(nested_equal(b, a))

        a = MyDummySet([1,2,3])
        a.add(4)
        b = MyDummySet([1,2,3,4])
        self.assertTrue(nested_equal(a, b))

        self.assertTrue(nested_equal(b, a))

        a = MyDummyList([1,2,3])
        a.append(4)
        b = MyDummyList([1,2,3,4])
        self.assertTrue(nested_equal(a, b))

        self.assertTrue(nested_equal(b, a))

        a = MyDummyMapping(a='b', c=42)
        b = MyDummyMapping(a='b', c=42)
        self.assertTrue(nested_equal(a, b))

        self.assertTrue(nested_equal(b, a))

        a = MyDummySet([1,2,3])
        a.add(4)
        b = MyDummySet([1,2,3,5])
        self.assertFalse(nested_equal(a, b))
        self.assertFalse(nested_equal(b, a))

        a = MyDummyList([1,2,3])
        a.append(5)
        b = MyDummyList([1,2,3,4])
        self.assertFalse(nested_equal(a, b))

        self.assertFalse(nested_equal(b, a))

        a = MyDummyMapping(a='b', c=a)
        b = MyDummyMapping(a='b', c=b)
        self.assertFalse(nested_equal(a, b))

        self.assertFalse(nested_equal(b, a))

        a = MyDummyCMP(42)
        b = MyDummyCMP(42)

        self.assertTrue(nested_equal(a, b))
        self.assertTrue(nested_equal(b, a))

        b = MyDummyCMP(1)

        self.assertFalse(nested_equal(a, b))

        self.assertFalse(nested_equal(b, a))

        self.assertFalse(nested_equal(a, 22))
        self.assertFalse(nested_equal(22, a))

        self.assertFalse(nested_equal(None, a))
        self.assertFalse(nested_equal(a, None))

        self.assertTrue(nested_equal(None, None))


class TestIteratorChain(unittest.TestCase):

    tags = 'unittest', 'utils', 'iterators'

    def test_next(self):
        l1 = (x for x in range(3))
        l2 = iter([3,4,5])
        l3 = iter([6])
        l4 = iter([7,8])

        chain = IteratorChain(l1, l2, l3)
        for irun in range(9):
            element = next(chain)
            self.assertEqual(irun, element)
            if irun == 4:
                chain.add(l4)

    def test_iter(self):
        l1 = (x for x in range(3))
        l2 = iter([3,4,5])
        l3 = iter([6])
        l4 = iter([7,8])

        chain = IteratorChain(l1, l2, l3)
        count = 0
        elem_list = []
        for elem in chain:
            self.assertEqual(elem, count)
            count += 1
            elem_list.append(elem)
            if count == 3:
                chain.add(l4)

        self.assertEqual(len(elem_list), 9)

class Slots1(HasSlots):
    __slots__ = 'hi'


class Slots2(Slots1):
    __slots__ = ['ho']


class Slots3(Slots2):
    __slots__ = ('hu', 'he')


class Slots4(Slots3):
    __slots__ = ()


class SlotsTest(unittest.TestCase):

    tags = 'unittest', 'utils', 'slots'

    def test_all_slots(self):
        slot = Slots4()
        all_slots = set(('hi', 'ho', 'hu', 'he', '__weakref__'))
        self.assertEqual(all_slots, slot.__all_slots__)

    def test_pickling(self):
        slot = Slots4()
        all_slots = set(('hi', 'ho', 'hu', 'he', '__weakref__'))
        new_slot = pickle.loads(pickle.dumps(slot))
        self.assertEqual(all_slots, new_slot.__all_slots__)


class MyCustomLeaf(SparseParameter):
    def __init__(self, full_name, data=None, comment=''):
        super(MyCustomLeaf, self).__init__(full_name, data, comment)
        self.v_my_property = 42


class MyCustomLeaf2(PickleParameter):

    __slots__ = 'v_my_property'

    def __init__(self, full_name, data=None, comment=''):
        super(MyCustomLeaf2, self).__init__(full_name, data, comment)
        self.v_my_property = 42


class NamingSchemeTest(unittest.TestCase):

    tags = 'unittest', 'utils', 'naming', 'slots'

    def test_v_property(self):
        cp = MyCustomLeaf('test')
        self.assertEqual(cp.vars.my_property, cp.v_my_property)
        with self.assertRaises(AttributeError):
            cp.v_my_other

    def test_v_property_slots(self):
        cp = MyCustomLeaf2('test')
        self.assertEqual(cp.vars.my_property, cp.v_my_property)
        with self.assertRaises(AttributeError):
            cp.v_my_other


class MyClass(object):
        def __init__(self, a, b, c, d=42):
            pass


class MyClassNoInit(object):
    pass


def kwargs_func(a, b, c=43, *args, **kwargs):
    pass


def argsfunc(a, b=42, *args):
    pass


def dummy(a, b, c, d=42):
    pass


class MatchingkwargsTest(unittest.TestCase):
    tags = 'unittest', 'utils', 'naming',  'argspec'

    def test_more_than_def(self):
        kwargs = dict(a=42, f=43)
        res = get_matching_kwargs(dummy, kwargs)
        self.assertEqual(len(res), 1)
        self.assertIn('a', res)
        self.assertEqual(res['a'], 42)

    def test_more_than_def_args(self):
        kwargs = dict(a=42, f=43)
        res = get_matching_kwargs(argsfunc, kwargs)
        self.assertEqual(len(res), 1)
        self.assertIn('a', res)
        self.assertEqual(res['a'], 42)

    def test_init_method(self):
        kwargs = dict(a=42, f=43)
        res = get_matching_kwargs(MyClass, kwargs)
        self.assertEqual(len(res), 1)
        self.assertIn('a', res)
        self.assertEqual(res['a'], 42)

    def test_no_match_no_init(self):
        kwargs = dict(a=42, f=43)
        res = get_matching_kwargs(MyClassNoInit, kwargs)
        self.assertEqual(len(res), 0)

    def test_kwargs(self):
        kwargs = dict(a=42, f=43)
        res = get_matching_kwargs(kwargs_func, kwargs)
        self.assertEqual(len(res), 2)
        self.assertIn('a', res)
        self.assertEqual(res['a'], 42)
        self.assertIn('f', res)
        self.assertEqual(res['f'], 43)



if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)


