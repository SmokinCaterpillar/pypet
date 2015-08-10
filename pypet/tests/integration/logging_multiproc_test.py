__author__ = 'Robert Meyer'


from pypet.tests.integration.logging_test import LoggingTest
from pypet.tests.testutils.ioutils import run_suite, parse_args



class MultiprocNoPoolQueueLoggingTest(LoggingTest):

    tags = 'integration', 'environment', 'logging', 'multiproc', 'nopool', 'queue'

    def set_mode(self):
        # import pypet.tests.testutils.ioutils as io
        # io.testParams['log_level'] = 40
        # io.testParams['remove'] = False
        super(MultiprocNoPoolQueueLoggingTest, self).set_mode()
        self.mode.multiproc = True
        self.mode.wrap_mode = 'QUEUE'
        self.mode.ncores = 3
        self.mode.use_pool = False


class MultiprocPoolLockLoggingTest(LoggingTest):

    tags = 'integration', 'environment', 'logging', 'multiproc', 'pool', 'lock'

    def set_mode(self):
        # import pypet.tests.testutils.ioutils as io
        # io.testParams['log_level'] = 40
        # io.testParams['remove'] = False
        super(MultiprocPoolLockLoggingTest, self).set_mode()
        self.mode.multiproc = True
        self.mode.wrap_mode = 'LOCK'
        self.mode.ncores = 2
        self.mode.use_pool = True


class MultiprocPoolQueueLoggingTest(LoggingTest):

    tags = 'integration', 'environment', 'logging', 'multiproc', 'pool', 'queue'

    def set_mode(self):
        # import pypet.tests.testutils.ioutils as io
        # io.testParams['log_level'] = 40
        # io.testParams['remove'] = False
        super(MultiprocPoolQueueLoggingTest, self).set_mode()
        self.mode.multiproc = True
        self.mode.wrap_mode = 'QUEUE'
        self.mode.ncores = 2
        self.mode.use_pool = True


    def test_logfile_old_way_disabling_mp_log(self):
        return super(MultiprocPoolQueueLoggingTest, self).test_logfile_old_way_disabling_mp_log()


class MultiprocNoPoolLockLoggingTest(LoggingTest):

    tags = 'integration', 'environment', 'logging', 'multiproc', 'nopool', 'lock'

    def set_mode(self):
        # import pypet.tests.testutils.ioutils as io
        # io.testParams['log_level'] = 40
        # io.testParams['remove'] = False
        super(MultiprocNoPoolLockLoggingTest, self).set_mode()
        self.mode.multiproc = True
        self.mode.wrap_mode = 'LOCK'
        self.mode.ncores = 4
        self.mode.use_pool = False


if __name__ == '__main__':
    opt_args = parse_args()
    run_suite(**opt_args)