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

TEST_IMPORT_ERRORS = ('ModuleImportFailure')

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


class UniversalSet(Set):
    def __len__(self):
        return 1

    def __contains__(self, key):
        return True

    def __iter__(self):
        raise StopIteration('No elements')

    def __reversed__(self):
        return self

    def __eq__(self, other):
        if isinstance(other, UniversalSet):
            return True

    def __or__(self, other):
        return self

    def __and__(self, other):
        return other

    def __rand__(self, other):
        return other

    def __ror__(self, other):
        return self


class TagTestDiscoverer(unittest.TestLoader, HasLogger):
    def __init__(self, tags_include=UniversalSet(),
                 tags_exclude=(),
                 tests_include=(),
                 tests_exclude=(),
                 order = ('tags_include', 'tags_exclude', 'tests_include', 'tests_exclude')):
        super(TagTestDiscoverer, self).__init__()
        self.tags_include = self._input2set(tags_include)
        self.tags_exclude = self._input2set(tags_exclude)
        self.tests_include = self._input2set(tests_include)
        self.tests_exclude = self._input2set(tests_exclude)
        self.order = order
        self._set_logger()

    @staticmethod
    def _input2set(element):
        if isinstance(element, UniversalSet):
            return element
        elif isinstance(element, compat.base_type):
            return {element}
        elif element is None:
            return set()
        else:
            return set(element)

    @staticmethod
    def _flatten_suite(suite):
        res = []
        for case in suite:
            if isinstance(case, unittest.TestSuite):
                res.extend(TagTestDiscoverer._flatten_suite(case))
            elif isinstance(case, unittest.TestCase):
                res.append(case)
            else:
                raise RuntimeError('You shall not pass')
        return res

    def discover(self, start_dir, pattern='test*.py', top_level_dir=None):
        tmp_suite = super(TagTestDiscoverer, self).discover(start_dir=start_dir, pattern=pattern,
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
            combined_name = class_name + '.' + test_name

            if case in found_set:
                continue
            else:
                found_set.add(case)

            if class_name == 'ModuleImportFailure':
                self._logger.error('ERROR could not import `%s`' % test_name)
            if class_name == 'LoadTestsFailure':
                self._logger.error('ERROR could not load test `%s`' % test_name)

            add = False
            for what in self.order:
                if what == 'tags_include':
                    if bool(tags & self.tags_include):
                        add = True
                elif what == 'tags_exclude':
                    if bool(tags & self.tags_exclude):
                        add = False

                elif what == 'tests_include':
                    if (class_name in self.tests_include or
                            test_name in self.tests_include or
                            combined_name in self.tests_include):
                        add = True
                elif what == 'tests_exclude':
                    if (class_name in self.tests_exclude or
                            test_name in self.tests_exclude or
                            combined_name in self.tests_exclude):
                        add = False
                else:
                    raise ValueError('Your order `%s` is not understood.' % what)

            if add:
                test_list.append(case)
        test_list = sorted(test_list)
        res_suite.addTests(test_list)
        return res_suite


def do_tag_discover(tags_include=UniversalSet(),
                 tags_exclude=(),
                 tests_include=(),
                 tests_exclude=()):
    loader = TagTestDiscoverer(tags_include=tags_include, tags_exclude=tags_exclude,
                              tests_include=tests_include, tests_exclude=tests_exclude)
    suite = loader.discover(start_dir='./', pattern='*test.py')
    return suite