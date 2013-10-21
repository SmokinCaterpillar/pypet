__author__ = 'Robert Meyer'

from pypet import pypetconstants
from hdf5_storage_test import EnvironmentTest, ResultSortTest
from test_helpers import make_run

class MultiprocQueueTest(EnvironmentTest):

    def set_mode(self):
        self.mode = pypetconstants.WRAP_MODE_QUEUE
        self.multiproc = True
        self.ncores = 3


class MultiprocLockTest(EnvironmentTest):

     def set_mode(self):
        self.mode = pypetconstants.WRAP_MODE_LOCK
        self.multiproc = True
        self.ncores = 3

class MultiprocSortQueueTest(ResultSortTest):

    def set_mode(self):
        self.mode = pypetconstants.WRAP_MODE_QUEUE
        self.multiproc = True
        self.ncores = 4


class MultiprocSortLockTest(ResultSortTest):

     def set_mode(self):
        self.mode = pypetconstants.WRAP_MODE_LOCK
        self.multiproc = True
        self.ncores = 4





if __name__ == '__main__':
    make_run()