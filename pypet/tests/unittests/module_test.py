__author__ = 'Robert Meyer'


import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

import pypet
from pypet import *
from pypet.tests.testutils.ioutils import get_root_logger, run_suite, parse_args

import logging
import inspect


class TestAllImport(unittest.TestCase):

    tags = 'unittest', 'import'

    def test_import_star(self):
        for class_name in pypet.__all__:
            logstr = 'Evaulauting %s: %s' % (class_name, repr(eval(class_name)))
            get_root_logger().info(logstr)

    def test_if_all_is_complete(self):
        for item in pypet.__dict__.values():
            if inspect.isclass(item) or inspect.isfunction(item):
                self.assertTrue(item.__name__ in pypet.__all__)

if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)