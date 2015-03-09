__author__ = 'Robert Meyer'

import getopt
import sys


from pypet.tests.testutils.ioutils import run_suite, discover_tests, TEST_IMPORT_ERROR


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
    suite = discover_tests(predicate= lambda class_name, test_name, tags:
                                                class_name != TEST_IMPORT_ERROR)
    run_suite(remove, folder, suite=suite)