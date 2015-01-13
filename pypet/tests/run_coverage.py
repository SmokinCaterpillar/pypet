__author__ = 'Robert Meyer'
import sys
pypetpath='/'
sys.path.append(pypetpath)
print('Appended path `%s`' % pypetpath)


import getopt
import os

from pypet.tests.all_single_core_tests import *

from pypet.tests.all_multi_core_tests import TestMPImmediatePostProc,\
    MultiprocLinkNoPoolLockTest, MultiprocLinkNoPoolQueueTest, MultiprocLinkLockTest,\
    MultiprocLinkQueueTest


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