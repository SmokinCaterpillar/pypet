__author__ = 'robert'


import sys
if (sys.version_info < (2, 7, 0)):
    import unittest2 as unittest
else:
    import unittest

try:
    import brian
    import pypet.brian
    from pypet.brian import *
except ImportError as exc:
    #print('Import Error: %s' % str(exc))
    brian = None

try:
    from importlib import reload
except ImportError:
    try:
        from imp import reload
    except ImportError:
        pass

from pypet.tests.testutils.ioutils import get_root_logger, parse_args, run_suite

import inspect


@unittest.skipIf(brian is None, 'Can only be run with brian!')
class TestAllBrianImport(unittest.TestCase):

    tags = 'unittest', 'brian', 'import'

    def test_import_star(self):
        for class_name in pypet.brian.__all__:
            logstr = 'Evaluauting %s: %s' % (class_name, repr(eval(class_name)))
            get_root_logger().info(logstr)

    def test_if_all_is_complete(self):
        for item in pypet.brian.__dict__.values():
            if inspect.isclass(item) or inspect.isfunction(item):
                self.assertTrue(item.__name__ in pypet.brian.__all__)

    def test_import_net_module(self):
        reload(pypet.brian.network)

if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)