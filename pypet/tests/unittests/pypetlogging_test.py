__author__ = 'Robert Meyer'

import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

try:
    import cPickle as pickle
except ImportError:
    import pickle

from pypet.pypetlogging import LoggingManager
from pypet.tests.testutils.ioutils import get_log_config
from pypet.utils.comparisons import nested_equal

class FakeTraj(object):
    def __init__(self):
        self.v_environment_name = 'env'
        self.v_name = 'traj'
        self.v_crun_ = 'run'


class LoggingManagerTest(unittest.TestCase):

    def test_pickling(self):
        manager = LoggingManager(log_config=get_log_config(), log_stdout=True,
                                 trajectory=FakeTraj())
        manager.check_log_config()
        manager.make_logging_handlers_and_tools()
        dump = pickle.dumps(manager)
        new_manager = pickle.loads(dump)
        manager.finalize()
