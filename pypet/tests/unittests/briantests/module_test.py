__author__ = 'robert'


import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

import pypet.brian
from pypet.brian import *

import logging
import inspect


class TestAllBrianImport(unittest.TestCase):

    def setUp(self):
        logging.basicConfig(level=logging.INFO)

    def test_import_star(self):
        for class_name in pypet.brian.__all__:
            logstr = 'Evaulauting %s: %s' % (class_name, repr(eval(class_name)))
            logging.getLogger().info(logstr)

    def test_if_all_is_complete(self):
        for item in pypet.brian.__dict__.values():
            if inspect.isclass(item) or inspect.isfunction(item):
                self.assertTrue(item.__name__ in pypet.brian.__all__)