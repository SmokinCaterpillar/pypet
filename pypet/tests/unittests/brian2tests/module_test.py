__author__ = 'robert'


import sys
import unittest

try:
    import brian2
    import pypet.brian2
    from pypet.brian2 import *
except ImportError as exc:
    #print('Import Error: %s' % str(exc))
    brian2 = None

from pypet.tests.testutils.ioutils import get_root_logger, parse_args, run_suite

import inspect


@unittest.skipIf(brian2 is None, 'Can only be run with brian!')
class TestAllBrian2Import(unittest.TestCase):

    tags = 'unittest', 'brian2', 'import'

    def test_import_star(self):
        for class_name in pypet.brian2.__all__:
            logstr = 'Evaluauting %s: %s' % (class_name, repr(eval(class_name)))
            get_root_logger().info(logstr)

    def test_if_all_is_complete(self):
        for item in pypet.brian2.__dict__.values():
            if inspect.isclass(item) or inspect.isfunction(item):
                self.assertTrue(item.__name__ in pypet.brian2.__all__)

if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)