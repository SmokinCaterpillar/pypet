__author__ = 'Robert Meyer'

import logging
import os
import random
import sys
import unittest
import configparser as cp
import shutil
import getopt
import tempfile
import time
try:
    import zmq
except ImportError:
    zmq = None

import pypet.pypetconstants as pypetconstants
from pypet import HasLogger
from pypet.pypetlogging import LoggingManager, rename_log_file
from pypet.utils.decorators import copydoc
from pypet.utils.helpful_functions import port_to_tcp


testParams=dict(
    tempdir = 'tmp_pypet_tests',
    # Temporary directory for the hdf5 files'''
    remove=True,
    # Whether or not to remove the temporary directory after the tests
    actual_tempdir='',
    # Actual temp dir, maybe in tests folder or in `tempfile.gettempdir()`
    user_tempdir='',
    # Specified log level
    log_config='test'
)

TEST_IMPORT_ERROR = 'ModuleImportFailure'

generic_log_folder = None


def errwrite(text):
    """Writes to stderr with linebreak"""
    sys.__stderr__.write(text + '\n')


def get_root_logger():
    """Returns root logger"""
    return logging.getLogger()


def get_log_config():
    """Returns the log config"""
    return testParams['log_config']


def get_log_path(traj, process_name=None):
    """Returns the path to the log files based on trajectory name etc."""
    return rename_log_file(generic_log_folder, trajectory=traj, process_name=process_name)


def get_random_port_url():
    """Determines the local server url with a random port"""
    url = port_to_tcp()
    errwrite('USING URL: %s \n' % url)
    return url


def prepare_log_config():
    """Prepares the test logging init files and creates parsers."""
    conf = testParams['log_config']

    pypet_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
    init_path = os.path.join(pypet_path, 'logging')

    if conf == 'test':
        conf_file = os.path.join(init_path, 'test.ini')
        conf_parser = handle_config_file(conf_file)
        conf = conf_parser
    elif conf == 'debug':
        conf_file = os.path.join(init_path, 'debug.ini')
        conf_parser = handle_config_file(conf_file)
        conf = conf_parser

    testParams['log_config'] = conf


def _rename_filename(filename):
    """Replaces the $temp$ wildcard in a filename"""
    global generic_log_folder

    if not filename.startswith('$temp'):
        raise ValueError('$temp must be at the beginning of the filename!')
    temp_folder = make_temp_dir('logs')
    filename = filename.replace('$temp', '')
    filename = os.path.join(temp_folder, filename)
    filename = os.path.normpath(filename)
    if generic_log_folder is None:
        generic_log_folder = os.path.dirname(filename)
    return filename


def handle_config_file(config_file):
    """Searches for the $temp wildcard in a given config file and replaces it."""
    parser = cp.ConfigParser()
    parser.read(config_file)
    sections = parser.sections()
    for section in sections:
        options = parser.options(section)
        for option in options:
            arg = parser.get(section, option, raw=True)
            if '$temp' in arg:
                LoggingManager._check_and_replace_parser_args(parser, section, option,
                                                              rename_func=_rename_filename,
                                                              make_dirs=False)
    return parser


def make_temp_dir(filename, signal=False):
    """Creates a temporary folder and returns the joined filename"""
    try:

        if ((testParams['user_tempdir'] is not None and testParams['user_tempdir'] != '') and
                        testParams['actual_tempdir'] == ''):
            testParams['actual_tempdir'] = testParams['user_tempdir']

        if not os.path.isdir(testParams['actual_tempdir']):
            os.makedirs(testParams['actual_tempdir'])

        return os.path.join(testParams['actual_tempdir'], filename)
    except OSError as exc:
        actual_tempdir = os.path.join(tempfile.gettempdir(), testParams['tempdir'])

        if signal:
            errwrite('I used `tempfile.gettempdir()` to create the temporary folder '
                             '`%s`.' % actual_tempdir)
        testParams['actual_tempdir'] = actual_tempdir
        if not os.path.isdir(testParams['actual_tempdir']):
            try:
                os.makedirs(testParams['actual_tempdir'])
            except Exception:
                pass # race condition

        return os.path.join(actual_tempdir, filename)
    except:
        get_root_logger().error('Could not create a directory.')
        raise


def run_suite(remove=None, folder=None, suite=None):
    """Runs a particular test suite or simply unittest.main.

    Takes care that all temporary data in `folder` is removed if `remove=True`.

    """
    if remove is not None:
        testParams['remove'] = remove

    testParams['user_tempdir'] = folder

    prepare_log_config()

    # Just signal if make_temp_dir works
    make_temp_dir('tmp.txt', signal=True)

    success = False
    try:
        if suite is None:
            unittest.main(verbosity=2)
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
        get_root_logger().log(21, 'REMOVING ALL TEMPORARY DATA')
        shutil.rmtree(testParams['actual_tempdir'], True)


def make_trajectory_name(testcase):
    """Creates a trajectory name based on the current `testcase`"""

    testid = testcase.id()
    split_names = testid.split('.')
    #name = 'T__' + '__'.join(split_names[-2:]) + '__' + randintstr
    seed = len(testid) + int(10*time.time())
    random.seed(seed)
    randintstr = str(random.randint(0, 10 ** 5))
    name = 'T__' + split_names[-1] + '__' + randintstr

    maxlen = pypetconstants.HDF5_STRCOL_MAX_NAME_LENGTH - 22

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
        if isinstance(element, str):
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
            test_name = str(case).split(' ')[0]
            class_name = case.__class__.__name__
            if not hasattr(case, 'tags'):
                tags = set()
            else:
                tags = self._input2set(case.tags)

            combined = (class_name, test_name, tuple(tags))
            if combined in found_set:
                continue
            else:
                found_set.add(combined)

            if class_name == 'ModuleImportFailure':
                self._logger.error('Could not import `%s`, I will skip the tests.' % test_name)
            if class_name == 'LoadTestsFailure':
                self._logger.error('Could not load test `%s`, maybe this is an ERROR. '
                                   'I will skip the test.' % test_name)

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
    opt_list, _ = getopt.getopt(sys.argv[1:],'k',['folder=', 'suite='])
    opt_dict = {}

    for opt, arg in opt_list:
        if opt == '-k':
            opt_dict['remove'] = False
            errwrite('I will keep all files.')

        if opt == '--folder':
            opt_dict['folder'] = arg
            errwrite('I will put all data into folder `%s`.' % arg)

        if opt == '--suite':
            opt_dict['suite_no'] = arg
            errwrite('I will run suite `%s`.' % arg)

    sys.argv = [sys.argv[0]]
    return opt_dict

# Prepare config on loading, just in case tests are not called via run_suite()
prepare_log_config()