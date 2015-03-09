__author__ = 'Robert Meyer'

import logging
logging.basicConfig(level=logging.INFO)

from collections import Set

import pypet.pypetconstants
import pypet.compat as compat
from pypet import HasLogger
import os

import random

import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

import shutil

import tempfile

testParams=dict(
    tempdir = 'tmp_pypet_tests',
    #''' Temporary directory for the hdf5 files'''
    remove=True,
    #''' Whether or not to remove the temporary directory after the tests'''
    actual_tempdir='',
    #''' Actual temp dir, maybe in tests folder or in `tempfile.gettempdir()`'''
    user_tempdir='',
    #'''If the user specifies in run all test a folder, this variable will be used'''
)

TEST_IMPORT_ERRORS = 'ModuleImportFailure'

def make_temp_file(filename):
    global testParams
    try:

        if ((testParams['user_tempdir'] is not None and testParams['user_tempdir'] != '') and
                        testParams['actual_tempdir'] == ''):
            testParams['actual_tempdir'] = testParams['user_tempdir']

        if not os.path.isdir(testParams['actual_tempdir']):
            os.makedirs(testParams['actual_tempdir'])

        return os.path.join(testParams['actual_tempdir'], filename)
    except OSError:
        logging.getLogger('').warning('Cannot create a temp file in the specified folder `%s`. ' %
                                    testParams['actual_tempdir'] +
                                    ' I will use pythons gettempdir method instead.')
        actual_tempdir = os.path.join(tempfile.gettempdir(), testParams['tempdir'])
        testParams['actual_tempdir'] = actual_tempdir
        return os.path.join(actual_tempdir,filename)
    except:
        logging.getLogger('').error('Could not create a directory. Sorry cannot run them')
        raise

def make_run(remove=None, folder=None, suite=None):

    global testParams

    if remove is not None:
        testParams['remove'] = remove

    testParams['user_tempdir'] = folder

    try:
        if suite is None:
            unittest.main()
        else:
            runner = unittest.TextTestRunner(verbosity=2)
            runner.run(suite)
    finally:
        remove_data()

def combined_suites(*test_suites):
    """Combines several suites into one"""
    combined_suite = unittest.TestSuite(test_suites)
    return combined_suite

def combine_tests(*tests):
    """ Puts given test classes into a combined suite"""
    loader = unittest.TestLoader()
    suites_list = []
    for test in tests:
        if test is not None:
            suite = loader.loadTestsFromTestCase(test)
            suites_list.append(suite)
    return combined_suites(*suites_list)

def remove_data():
    global testParams
    if testParams['remove']:
        print('REMOVING ALL TEMPORARY DATA')
        shutil.rmtree(testParams['actual_tempdir'], True)

def make_trajectory_name(testcase):
    """Creates a trajectory name best on the current `testcase`"""
    name = 'T'+testcase.id()[12:].replace('.','_')+ '_'+str(random.randint(0,10**4))
    maxlen = pypet.pypetconstants.HDF5_STRCOL_MAX_NAME_LENGTH-22

    if len(name) > maxlen:
        name = name[len(name)-maxlen:]

        while name.startswith('_'):
            name = name[1:]

    return name


class LambdaTestDiscoverer(unittest.TestLoader, HasLogger):
    def __init__(self, predicate=None):
        super(LambdaTestDiscoverer, self).__init__()
        if predicate is not None:
            self.predicate=predicate
        else:
            self.predicate = lambda x, y, z: True
        self._set_logger()

    @staticmethod
    def _input2set(element):
        if isinstance(element, compat.base_type):
            return set([element])
        elif element is None:
            return set()
        else:
            return set(element)

    @staticmethod
    def _flatten_suite(suite):
        res = []
        for case in suite:
            if isinstance(case, unittest.TestSuite):
                res.extend(LambdaTestDiscoverer._flatten_suite(case))
            else:
                res.append(case)
        return res

    def discover(self, start_dir, pattern='test*.py', top_level_dir=None):
        tmp_suite = super(LambdaTestDiscoverer, self).discover(start_dir=start_dir, pattern=pattern,
                                                        top_level_dir=top_level_dir)

        res_suite = unittest.TestSuite()
        flattened_suite = self._flatten_suite(tmp_suite)
        found_set = set()
        test_list = []
        for case in flattened_suite:
            if not hasattr(case, 'tags'):
                tags = set()
            else:
                tags = self._input2set(case.tags)
            test_name = str(case).split(' ')[0]
            class_name = case.__class__.__name__

            if case in found_set:
                continue
            else:
                found_set.add(case)

            if class_name == 'ModuleImportFailure':
                self._logger.error('ERROR could not import `%s`' % test_name)
            if class_name == 'LoadTestsFailure':
                self._logger.error('ERROR could not load test `%s`' % test_name)

            add = self.predicate(class_name, test_name, tags)

            if add:
                test_list.append(case)

        combined_name_key = lambda key: key.__class__.__name__ + str(key).split(' ')[0]
        test_list = sorted(test_list, key = combined_name_key)
        res_suite.addTests(test_list)
        return res_suite


def do_tag_discover(predicate=None):
    loader = LambdaTestDiscoverer(predicate)
    start_dir = os.path.dirname(os.path.abspath(__file__))
    start_dir = os.path.abspath(os.path.join(start_dir, '..'))
    suite = loader.discover(start_dir=start_dir, pattern='*test.py')
    return suite