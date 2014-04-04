__author__ = 'robert'



# from pypet.tests.hdf5_multiproc_test import MultiprocQueueTest

from pypet.tests.hdf5_multiproc_test import  MultiprocLockTest,MultiprocQueueTest,MultiprocSortLockTest,MultiprocSortQueueTest, \
    MultiprocNoPoolLockTest,MultiprocNoPoolQueueTest,MultiprocNoPoolSortLockTest,MultiprocNoPoolSortQueueTest, CapTest

from pypet.tests.briantests.brian_full_network_test import NetworkTest, NetworkMPTest



from pypet.tests.test_helpers import make_run

import sys

import getopt

from unittest import TestCase

class Dummy(TestCase):
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
            print 'I will put all data into folder `%s`.' % folder

    sys.argv=[sys.argv[0]]
    make_run(remove, folder)