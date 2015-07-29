__author__ = 'Robert Meyer'

import pypet.pypetconstants as pypetconstants
from pypet.tests.integration.link_test import LinkEnvironmentTest
from pypet.tests.testutils.ioutils import parse_args, run_suite
try:
    import psutil
except ImportError:
    psutil = None


class MultiprocLinkQueueTest(LinkEnvironmentTest):

    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'queue', 'pool', 'links'

    def set_mode(self):
        LinkEnvironmentTest.set_mode(self)
        self.mode = pypetconstants.WRAP_MODE_QUEUE
        self.multiproc = True
        self.log_stdout = True
        if psutil is not None:
            self.ncores = 0
        else:
            self.ncores = 3
        self.use_pool=True


class MultiprocLinkLocalTest(LinkEnvironmentTest):

    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'local', 'pool', 'links'

    def set_mode(self):
        LinkEnvironmentTest.set_mode(self)
        self.mode = pypetconstants.WRAP_MODE_LOCAL
        self.multiproc = True
        self.log_stdout = True
        self.use_pool=True


class MultiprocLinkLockTest(LinkEnvironmentTest):

    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'lock', 'pool', 'links'

    # def test_run(self):
    #     super(MultiprocLockTest, self).test_run()

    def set_mode(self):
        LinkEnvironmentTest.set_mode(self)
        self.mode = pypetconstants.WRAP_MODE_LOCK
        self.multiproc = True
        self.ncores = 4
        self.use_pool=True


class MultiprocLinkNoPoolQueueTest(LinkEnvironmentTest):

    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'queue', 'nopool', 'links'

    def set_mode(self):
        LinkEnvironmentTest.set_mode(self)
        self.mode = pypetconstants.WRAP_MODE_QUEUE
        self.multiproc = True
        self.ncores = 3
        self.use_pool=False


class MultiprocLinkNoPoolLockTest(LinkEnvironmentTest):

    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'lock', 'nopool', 'links'

    def set_mode(self):
        LinkEnvironmentTest.set_mode(self)
        self.mode = pypetconstants.WRAP_MODE_LOCK
        self.multiproc = True
        self.ncores = 2
        self.use_pool=False


if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)