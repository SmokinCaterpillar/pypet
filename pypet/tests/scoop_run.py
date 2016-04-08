__author__ = 'robert'

try:
    import pypet
except ImportError:
    import sys
    sys.path.append('/media/data/PYTHON_WORKSPACE/pypet-project')

import scoop

from pypet.tests.testutils.ioutils import discover_tests, parse_args, run_suite
from pypet.tests.integration.environment_scoop_test import check_mock

scoop_suite = discover_tests(lambda  class_name, test_name, tags: 'scoop' in tags)


if __name__ == '__main__':
    mock = check_mock()
    if mock:
        raise RuntimeError('Not running in SCOOP mode!')
    opt_dict = parse_args()
    run_suite(suite=scoop_suite, **opt_dict)