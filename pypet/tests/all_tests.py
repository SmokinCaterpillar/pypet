__author__ = 'Robert Meyer'

import getopt
import sys
import os

from pypet.tests.all_single_core_tests import *
# if not (sys.version_info < (2, 7, 0)):
#     # Test MP only for python 2.7 due to time constraints of travis-ci
from pypet.tests.all_multi_core_tests import *
# else:
#     print('Skipping MP Tests')

# # Works only if someone has installed Brian
# try:
#     from pypet.tests.briantests.brian_parameter_test import BrianParameterTest, BrianParameterStringModeTest, \
#         BrianResult, BrianResultStringModeTest
#     # if not os.getenv('TRAVIS', False):
#     from pypet.tests.briantests.brian_monitor_test import BrianMonitorTest
#     from pypet.tests.briantests.brian_full_network_test import BrianFullNetworkTest, BrianFullNetworkMPTest
# except ImportError as e:
#     print(repr(e))
#     pass


if __name__ == '__main__':
    opt_list, _ = getopt.getopt(sys.argv[1:],'k',['folder='])
    remove = None
    folder = None
    for opt, arg in opt_list:
        if opt == '-k':
            remove = False
            print('I will keep all files.')

        if opt == '--folder':
            folder = arg
            print('I will put all data into folder `%s`.' % folder)

    sys.argv=[sys.argv[0]]
    make_run(remove, folder)