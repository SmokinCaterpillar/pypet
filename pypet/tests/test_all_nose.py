__author__ = 'Robert Meyer'

import getopt
import sys
import os
import sys
import unittest

from pypet.tests.testutils.ioutils import discover_tests, TEST_IMPORT_ERROR

class NoseTestDummy(unittest.TestCase):
    pass

suite = discover_tests(predicate= lambda class_name, test_name, tags:
                                                class_name != TEST_IMPORT_ERROR)
suite_dict = {}
for case in suite:
    class_name = case.__class__.__name__
    globals()[class_name] = case.__class__

