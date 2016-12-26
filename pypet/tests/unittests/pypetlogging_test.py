__author__ = 'Robert Meyer'

import sys
import unittest

import pickle

from pypet.pypetlogging import LoggingManager
from pypet.tests.testutils.ioutils import get_log_config, run_suite, parse_args
from pypet.utils.comparisons import nested_equal

class FakeTraj(object):
    def __init__(self):
        self.v_environment_name = 'env'
        self.v_name = 'traj'

    def f_wildcard(self, card):
        return 'Ladida'


class LoggingManagerTest(unittest.TestCase):

    tags = 'logging', 'unittest', 'pickle'

    def test_pickling(self):
        manager = LoggingManager(log_config=get_log_config(), log_stdout=True)
        manager.extract_replacements(FakeTraj())
        manager.check_log_config()
        manager.make_logging_handlers_and_tools()
        dump = pickle.dumps(manager)
        new_manager = pickle.loads(dump)
        manager.finalize()


if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)
