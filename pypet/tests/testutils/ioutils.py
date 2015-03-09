__author__ = 'Robert Meyer'

import logging
rootlogger = logging.getLogger()

import pypet.pypetconstants
import pypet.compat as compat
from pypet import HasLogger
from pypet.utils.decorators import copydoc
import os

import random

import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

import shutil
import getopt
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
    log_level=logging.INFO
)

TEST_IMPORT_ERROR = 'ModuleImportFailure'


def get_log_level():
    """Simply returns the user chosen log-level"""
    return testParams['log_level']


def make_temp_file(filename):
    """Creates a temporary file in a temporary folder"""
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


def run_suite(remove=None, folder=None, suite=None, log_level=None):
    """Runs a particular test suite or simply unittest.main.

    Takes care that all temporary data in `folder` is removed if `remove=True`.

    You can also define a global `log_level`.

    """
    global testParams

    if remove is not None:
        testParams['remove'] = remove

    testParams['user_tempdir'] = folder

    if log_level is not None:
        testParams['log_level'] = log_level
    logging.basicConfig(level=testParams['log_level'])

    success = False
    try:
        if suite is None:
            unittest.main()
        else:
            runner = unittest.TextTestRunner(verbosity=2)
            result = runner.run(suite)
            success = result.wasSuccessful()
    finally:
        remove_data()

    if not success:
        # Exit with 1 if tests were not successful
        sys.exit(1)


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
    """Removes all data from temporary folder"""
    global testParams
    if testParams['remove']:
        rootlogger.info('REMOVING ALL TEMPORARY DATA')
        shutil.rmtree(testParams['actual_tempdir'], True)


def make_trajectory_name(testcase):
    """Creates a trajectory name based on the current `testcase`"""
    name = 'T'+testcase.id()[12:].replace('.','_')+ '_'+str(random.randint(0,10**4))
    maxlen = pypet.pypetconstants.HDF5_STRCOL_MAX_NAME_LENGTH-22

    if len(name) > maxlen:
        name = name[len(name)-maxlen:]

        while name.startswith('_'):
            name = name[1:]

    return name


class LambdaTestDiscoverer(unittest.TestLoader, HasLogger):
    """ Discovers tests and filters according to a `predicate`.

    Note that tests are discovered first and then filtered.
    This means all tests have already been instantiated at time of filtering.

    `predicate` must accept three variables `class_name`, name of test class,
    `test_name`, name of the individual test, `tags`, the set of tags assigned
    to the test class.

    For instance:

         >>> my_pred = lambda class_name, test_name, tags: class_name != 'MyTestClass' and 'mytag' in tags
         >>> loader = LambdaTestDiscoverer(my_pred)

    """
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

    @copydoc(unittest.TestLoader.discover)
    def discover(self, start_dir, pattern='test*.py', top_level_dir=None):
        tmp_suite = super(LambdaTestDiscoverer, self).discover(start_dir=start_dir, pattern=pattern,
                                                        top_level_dir=top_level_dir)

        res_suite = unittest.TestSuite()
        flattened_suite = self._flatten_suite(tmp_suite)
        found_set = set()
        test_list = []
        for case in flattened_suite:
            if case in found_set:
                continue
            else:
                found_set.add(case)

            if not hasattr(case, 'tags'):
                tags = set()
            else:
                tags = self._input2set(case.tags)
            test_name = str(case).split(' ')[0]
            class_name = case.__class__.__name__

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


def discover_tests(predicate=None):
    """Builds a LambdaTestLoader and discovers tests according to `predicate`."""
    loader = LambdaTestDiscoverer(predicate)
    start_dir = os.path.dirname(os.path.abspath(__file__))
    start_dir = os.path.abspath(os.path.join(start_dir, '..'))
    suite = loader.discover(start_dir=start_dir, pattern='*test.py')
    return suite


def parse_args():
    """Parses arguments and returns a dictionary"""
    opt_list, _ = getopt.getopt(sys.argv[1:],'k',['folder=', 'suite=', 'loglevel='])
    opt_dict = {}

    for opt, arg in opt_list:
        if opt == '-k':
            opt_dict['remove'] = False
            print('I will keep all files.')

        if opt == '--folder':
            opt_dict['folder'] = arg
            print('I will put all data into folder `%s`.' % arg)

        if opt == '--suite':
            opt_dict['suite_no'] = arg
            print('I will run suite `%s`.' % arg)

        if opt == '--loglevel':
            opt_dict['log_level'] = int(arg)
            print('Using log level %s.' % arg)

    sys.argv=[sys.argv[0]]
    return opt_dict