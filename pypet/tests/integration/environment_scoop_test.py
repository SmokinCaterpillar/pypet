__author__ = 'Robert Meyer'


try:
    import scoop
except ImportError:
    scoop = None


def scoop_not_functional_check():
    if scoop is not None and scoop.IS_RUNNING:
        print('SCOOP mode functional!')
        return False
    else:
        print('SCOOP NOT running!')
        return True


from pypet.tests.integration.environment_test import EnvironmentTest, ResultSortTest
from pypet.tests.integration.environment_multiproc_test import check_nice
import pypet.pypetconstants as pypetconstants
from pypet.tests.testutils.ioutils import parse_args, run_suite
from pypet.tests.testutils.data import unittest


@unittest.skipIf(scoop_not_functional_check(), 'Only makes sense if scoop is installed and running')
class MultiprocSCOOPNetqueueTest(EnvironmentTest):

    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'netqueue', 'scoop'

    def set_mode(self):
        super(MultiprocSCOOPNetqueueTest, self).set_mode()
        self.mode = pypetconstants.WRAP_MODE_NETQUEUE
        self.multiproc = True
        self.freeze_input = False
        self.ncores = 4
        self.gc_interval = 3
        self.niceness = check_nice(1)
        self.use_pool = False
        self.use_scoop = True
        self.graceful_exit = False

    @unittest.skip('Does not work with scoop (fully), because scoop uses main frame.')
    def test_niceness(self):
        pass

    # def test_run(self):
    #     return super(MultiprocSCOOPLocalTest, self).test_run()


@unittest.skipIf(scoop_not_functional_check(), 'Only makes sense if scoop is installed')
class MultiprocSCOOPSortLocalTest(ResultSortTest):

    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'local', 'scoop'

    def set_mode(self):
        super(MultiprocSCOOPSortLocalTest, self).set_mode()
        self.mode = pypetconstants.WRAP_MODE_LOCAL
        self.freeze_input = False
        self.multiproc = True
        self.ncores = 4
        self.use_pool = False
        self.use_scoop = True
        self.graceful_exit = False

    @unittest.skip('Does not work with SCOOP')
    def test_graceful_exit(self):
        pass


@unittest.skipIf(scoop_not_functional_check(), 'Only makes sense if scoop is installed')
class MultiprocFrozenSCOOPLocalTest(EnvironmentTest):

    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'local', 'scoop', 'freeze_input'

    def set_mode(self):
        super(MultiprocFrozenSCOOPLocalTest, self).set_mode()
        self.mode = pypetconstants.WRAP_MODE_LOCAL
        self.multiproc = True
        self.freeze_input = True
        self.ncores = 4
        self.gc_interval = 3
        self.niceness = check_nice(1)
        self.use_pool = False
        self.use_scoop = True
        self.graceful_exit = False

    @unittest.skip('Does not work with scoop (fully), because scoop uses main frame.')
    def test_niceness(self):
        pass

    # def test_run(self):
    #     return super(MultiprocSCOOPLocalTest, self).test_run()


# @unittest.skipIf(scoop is None, 'Only makes sense if scoop is installed')
# class MultiprocFrozenSCOOPSortLocalTest(ResultSortTest):
#
#     tags = 'integration', 'hdf5', 'environment', 'multiproc', 'local', 'scoop', 'freeze_input'
#
#     def set_mode(self):
#         super(MultiprocFrozenSCOOPSortLocalTest, self).set_mode()
#         self.mode = pypetconstants.WRAP_MODE_LOCAL
#         self.freeze_input = True
#         self.multiproc = True
#         self.ncores = 4
#         self.use_pool = False
#         self.use_scoop = True


@unittest.skipIf(scoop_not_functional_check(), 'Only makes sense if scoop is installed')
class MultiprocFrozenSCOOPSortNetlockTest(ResultSortTest):

    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'netlock', 'scoop', 'freeze_input'

    def set_mode(self):
        super(MultiprocFrozenSCOOPSortNetlockTest, self).set_mode()
        self.mode = pypetconstants.WRAP_MODE_NETLOCK
        self.freeze_input = True
        self.multiproc = True
        self.ncores = 4
        self.use_pool = False
        self.use_scoop = True
        self.port = (10000, 60000)
        self.graceful_exit = False

    @unittest.skip('Does not work with SCOOP')
    def test_graceful_exit(self):
        pass


@unittest.skipIf(scoop_not_functional_check(), 'Only makes sense if scoop is installed')
class MultiprocFrozenSCOOPSortNetqueueTest(ResultSortTest):

    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'netqueue', 'scoop', 'freeze_input', 'mehmet'

    def set_mode(self):
        super(MultiprocFrozenSCOOPSortNetqueueTest, self).set_mode()
        self.mode = pypetconstants.WRAP_MODE_NETQUEUE
        self.freeze_input = True
        self.multiproc = True
        self.ncores = 4
        self.use_pool = False
        self.use_scoop = True
        self.graceful_exit = False
        #self.port = 'tcp://127.0.0.1:22334'

    @unittest.skip('Does not work with SCOOP')
    def test_graceful_exit(self):
        pass


# @unittest.skipIf(scoop is None, 'Only makes sense if scoop is installed')
# class MultiprocSCOOPNetqueueTest(EnvironmentTest):
#
#     tags = 'integration', 'hdf5', 'environment', 'multiproc', 'netqueue', 'scoop'
#
#     def set_mode(self):
#         super(MultiprocSCOOPNetqueueTest, self).set_mode()
#         self.mode = pypetconstants.WRAP_MODE_NETQUEUE
#         self.multiproc = True
#         self.freeze_input = False
#         self.ncores = 4
#         self.gc_interval = 3
#         self.niceness = check_nice(1)
#         self.use_pool = False
#         self.use_scoop = True
#         self.port = None
#         self.timeout = 9999.99


@unittest.skipIf(scoop_not_functional_check(), 'Only makes sense if scoop is installed')
class MultiprocSCOOPNetlockTest(EnvironmentTest):

    tags = 'integration', 'hdf5', 'environment', 'multiproc', 'netlock', 'scoop'

    def set_mode(self):
        super(MultiprocSCOOPNetlockTest, self).set_mode()
        self.mode = pypetconstants.WRAP_MODE_NETLOCK
        self.multiproc = True
        self.freeze_input = False
        self.ncores = 4
        self.gc_interval = 3
        self.niceness = check_nice(1)
        self.use_pool = False
        self.use_scoop = True
        self.port = None
        self.timeout = 1099.99
        self.graceful_exit = False
        # self.port = 'tcp://127.0.0.1:22334'

    @unittest.skip('Does not work with scoop (fully), because scoop uses main frame.')
    def test_niceness(self):
        pass


if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)
