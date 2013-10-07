__author__ = 'Robert Meyer'



import getopt
import sys
from environment_test import *
from hdf5_multiproc_test import *
from parameter_test import *
from speed_test import *
from trajectory_test import *
from hdf5_merge_test import *
from hdf5_removal_and_continue_tests import *
from utilstest import *
from environment_test import *
from test_helpers import run_tests

import os
# Works only if someone has installed Brian
try:
    from brian_parameter_test import *
    if not os.getenv('TRAVIS',False):
        from brian_full_network_test import *
except ImportError:
    pass


if __name__ == '__main__':
    opt_list, _ = getopt.getopt(sys.argv[1:],'k',['folder='])
    remove = None
    folder = None
    for opt, arg in opt_list:
        if opt == '-k':
            remove = False
            print 'I will keep all files.'

        if opt == '--folder':
            folder = arg
            print 'I will put all data into folder >>%s<<' % folder

    run_tests(remove, folder)