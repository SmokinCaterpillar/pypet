__author__ = 'Robert Meyer'


from pypet.tests.testutils.ioutils import run_suite, discover_tests, TEST_IMPORT_ERROR, parse_args

tests_include=set(('MultiprocNoPoolLockTest',
                   'MultiprocSortQueueTest',
                   'MultiprocLinkLockTest',
                   'CapTest',
                   'MultiprocStorageLockTest',
                   'MultiprocNoPoolQueueLoggingTest'))
big_suite_1 = discover_tests(lambda  class_name, test_name, tags: class_name in tests_include)

tests_include=set(('MultiprocNoPoolQueueTest',
                   'MultiprocSortLockTest',
                   'MultiprocLinkNoPoolLockTest',
                   'TestMPPostProc',
                   'ContinueMPPoolTest',
                   'MultiprocPoolLockLoggingTest'))
big_suite_2 = discover_tests(lambda  class_name, test_name, tags: class_name in tests_include)

tests_include=set(('MultiprocLockTest',
                   'MultiprocNoPoolSortQueueTest',
                   'MultiprocLinkNoPoolQueueTest',
                   'TestMPImmediatePostProc',
                   'MultiprocStorageNoPoolLockTest',
                   'MultiprocNoPoolLockLoggingTest'))
big_suite_3 = discover_tests(lambda  class_name, test_name, tags: class_name in tests_include)

tests_include=set(('MultiprocQueueTest',
                   'MultiprocNoPoolSortLockTest',
                   'MultiprocLinkQueueTest',
                   'ContinueMPTest',
                   'BrianFullNetworkMPTest',
                   'MultiprocPoolQueueLoggingTest'))
big_suite_4 = discover_tests(lambda  class_name, test_name, tags: class_name in tests_include)


suite_dict = {'1': big_suite_1, '2': big_suite_2, '3': big_suite_3, '4': big_suite_4}


if __name__ == '__main__':
    opt_dict = parse_args()
    suite = None
    if 'suite_no' in opt_dict:
        suite_no = opt_dict.pop('suite_no')
        suite = suite_dict[suite_no]

    if suite is None:
        pred = lambda class_name, test_name, tags: ('multiproc' in tags and
                                                    class_name != TEST_IMPORT_ERROR)
        suite = discover_tests(pred)

    run_suite(suite=suite, **opt_dict)