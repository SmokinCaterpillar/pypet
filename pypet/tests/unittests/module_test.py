__author__ = 'Robert Meyer'


import sys
import unittest

import pypet
from pypet import *
del test  # To not run all tests if this file is executed with nosetests
from pypet.tests.testutils.ioutils import get_root_logger, run_suite, parse_args

import logging
import inspect


class TestAllImport(unittest.TestCase):

    tags = 'unittest', 'import'

    def test_import_star(self):
        for class_name in pypet.__all__:
            if class_name == 'test':
                continue
            logstr = 'Evaulauting %s: %s' % (class_name, repr(eval(class_name)))
            get_root_logger().info(logstr)

    def test_if_all_is_complete(self):
        for item in pypet.__dict__.values():
            if inspect.isclass(item) or inspect.isfunction(item):
                self.assertTrue(item.__name__ in pypet.__all__)


class TestRunningTests(unittest.TestCase):

    tags = 'unittest', 'test', 'meta'

    def test_run_one_test(self):
        predicate = lambda class_name, test_name, tags:(test_name == 'test_import_star' and
                                                        class_name == 'TestAllImport')
        pypet.test(predicate=predicate)


if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)