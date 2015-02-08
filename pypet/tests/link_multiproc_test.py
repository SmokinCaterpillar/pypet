__author__ = 'robert'

import pypet.pypetconstants as pypetconstants
from pypet.tests.link_test import LinkEnvironmentTest

class MultiprocLinkQueueTest(LinkEnvironmentTest):

    def set_mode(self):
        LinkEnvironmentTest.set_mode(self)
        self.mode = pypetconstants.WRAP_MODE_QUEUE
        self.multiproc = True
        self.ncores = 0
        self.use_pool=True


class MultiprocLinkLockTest(LinkEnvironmentTest):

    # def test_run(self):
    #     super(MultiprocLockTest, self).test_run()

    def set_mode(self):
        LinkEnvironmentTest.set_mode(self)
        self.mode = pypetconstants.WRAP_MODE_LOCK
        self.multiproc = True
        self.ncores = 4
        self.use_pool=True



class MultiprocLinkNoPoolQueueTest(LinkEnvironmentTest):

    def set_mode(self):
        LinkEnvironmentTest.set_mode(self)
        self.mode = pypetconstants.WRAP_MODE_QUEUE
        self.multiproc = True
        self.ncores = 3
        self.use_pool=False


class MultiprocLinkNoPoolLockTest(LinkEnvironmentTest):


     def set_mode(self):
        LinkEnvironmentTest.set_mode(self)
        self.mode = pypetconstants.WRAP_MODE_LOCK
        self.multiproc = True
        self.ncores = 2
        self.use_pool=False