__author__ = 'Robert Meyer'

import getopt
import sys

from pypet.tests.testutils.ioutils import run_suite, discover_tests, TEST_IMPORT_ERROR

tests_include=set(('MultiprocNoPoolLockTest',
                   'MultiprocSortQueueTest',
                   'MultiprocLinkLockTest',
                   'CapTest',
                   'MultiprocStorageLockTest'))
big_suite_1 = discover_tests(lambda  class_name, test_name, tags: class_name in tests_include)

tests_include=set(('MultiprocNoPoolQueueTest',
                   'MultiprocSortLockTest',
                   'MultiprocLinkNoPoolLockTest',
                   'TestMPPostProc',
                   'ContinueMPPoolTest'))
big_suite_2 = discover_tests(lambda  class_name, test_name, tags: class_name in tests_include)

tests_include=set(('MultiprocLockTest',
                   'MultiprocNoPoolSortQueueTest',
                   'MultiprocLinkNoPoolQueueTest',
                   'TestMPImmediatePostProc',
                   'MultiprocStorageNoPoolLockTest'))
big_suite_3 = discover_tests(lambda  class_name, test_name, tags: class_name in tests_include)

tests_include=set(('MultiprocQueueTest',
                   'MultiprocNoPoolSortLockTest',
                   'MultiprocLinkQueueTest',
                   'ContinueMPTest',
                   'BrianFullNetworkMPTest'))
big_suite_4 = discover_tests(lambda  class_name, test_name, tags: class_name in tests_include)


suite_dict = {'1': big_suite_1, '2': big_suite_2, '3': big_suite_3, '4': big_suite_4}


if __name__ == '__main__':
    opt_list, _ = getopt.getopt(sys.argv[1:],'k',['folder=', 'suite='])
    remove = None
    folder = None
    suite = None

    for opt, arg in opt_list:
        if opt == '-k':
            remove = False
            print('I will keep all files.')

        if opt == '--folder':
            folder = arg
            print('I will put all data into folder `%s`.' % folder)

        if opt == '--suite':
            suite_no = arg
            print('I will run suite `%s`.' % suite_no)
            suite = suite_dict[suite_no]

    if suite is None:
        pred = lambda class_name, test_name, tags: ('multiproc' in tags and
                                                    class_name != TEST_IMPORT_ERROR)
        suite = discover_tests(pred)

    sys.argv=[sys.argv[0]]
    run_suite(remove, folder, suite)