__author__ = 'Robert Meyer'

import getopt
import sys
import os
import unittest

from pypet.tests.testutils.ioutils import do_tag_discover, TEST_IMPORT_ERRORS, make_run

class NoseTestDummy(unittest.TestCase):
    pass

suite = do_tag_discover(predicate= lambda class_name, test_name, tags:
                                                class_name != TEST_IMPORT_ERRORS)
suite_dict = {}
for case in suite:
    class_name = case.__class__.__name__
    globals()[class_name] = case.__class__

