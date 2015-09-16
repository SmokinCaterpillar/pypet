__author__ = 'Robert Meyer'


from pypet.tests.testutils.ioutils import run_suite, discover_tests, TEST_IMPORT_ERROR, parse_args

tests_include=set(('MultiprocNoPoolLockTest',
                   #'MultiprocNoPoolPipeTest',
                   'MultiprocPoolSortQueueTest',
                   'MultiprocFrozenPoolSortQueueTest',
                   'MultiprocLinkLockTest',
                   'CapTest',
                   # 'MultiprocPoolLockTest',
                   'MultiprocStorageLockTest',
                   'MultiprocNoPoolQueueLoggingTest',
                   'MultiprocFrozenPoolLocalTest',
                   'TestMPImmediatePostProcQueue',
                   'MultiprocNoPoolNetlockTest',
                   'MultiprocStorageNetlockTest',
                   'MultiprocSCOOPLocalTest'))
big_suite_1 = discover_tests(lambda  class_name, test_name, tags: class_name in tests_include and 'mehmet' in tags)

tests_include=set((#'MultiprocNoPoolQueueTest',
                   'MultiprocPoolQueueTest',
                   'MultiprocFrozenPoolPipeTest',
                   'MultiprocPoolSortLockTest',
                   'MultiprocPoolSortPipeTest',
                   'MultiprocFrozenPoolSortLockTest',
                   'MultiprocLinkNoPoolLockTest',
                   'TestMPPostProc',
                   'ContinueMPPoolTest',
                   'MultiprocPoolLockLoggingTest',
                   'MultiprocNoPoolSortLocalTest',
                   'TestMPImmediatePostProcLocal',
                   'MultiprocPoolSortNetlockTest',
                   'MultiprocSCOOPSortLocalTest'))
big_suite_2 = discover_tests(lambda  class_name, test_name, tags: class_name in tests_include and 'mehmet' in tags)

tests_include=set((#'MultiprocFrozenPoolLockTest',
                   'MultiprocNoPoolSortQueueTest',
                   'MultiprocLinkNoPoolQueueTest',
                   'MultiprocPoolSortPipeTest',
                   'TestMPImmediatePostProcLock',
                   #'MultiprocPoolPipeTest',
                   'MultiprocStorageNoPoolLockTest',
                   'MultiprocNoPoolLockLoggingTest',
                   'MultiprocFrozenSCOOPSortNetlockTest',
                   'MultiprocFrozenSCOOPSortLocalTest'))
big_suite_3 = discover_tests(lambda  class_name, test_name, tags: class_name in tests_include and 'mehmet' in tags)

tests_include=set(('MultiprocFrozenPoolQueueTest',
                   'MultiprocFrozenPoolSortPipeTest',
                   'MultiprocNoPoolSortLockTest',
                   'MultiprocLinkQueueTest',
                   'ContinueMPTest',
                   'BrianFullNetworkMPTest',
                   'MultiprocPoolQueueLoggingTest',
                   'MultiprocPoolSortLocalTest',
                   'MultiprocLinkLocalTest',
                   'TestMPImmediatePostProcPipe',
                   'MultiprocSCOOPNetlockTest',
                   'MultiprocNoPoolSortNetlockTest',
                   'MultiprocFrozenSCOOPLocalTest'))
big_suite_4 = discover_tests(lambda  class_name, test_name, tags: class_name in tests_include and 'mehmet' in tags)


suite_dict = {'1': big_suite_1, '2': big_suite_2, '3': big_suite_3, '4': big_suite_4}


if __name__ == '__main__':
    opt_dict = parse_args()
    suite = None
    if 'suite_no' in opt_dict:
        suite_no = opt_dict.pop('suite_no')
        suite = suite_dict[suite_no]

    if suite is None:
        pred = lambda class_name, test_name, tags: ('multiproc' in tags and
                                                    class_name != TEST_IMPORT_ERROR and 'mehmet' in tags)
        suite = discover_tests(pred)

    run_suite(suite=suite, **opt_dict)