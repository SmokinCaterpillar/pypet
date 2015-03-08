__author__ = 'Robert Meyer'

import getopt
import sys

from pypet.tests.testutils.ioutils import make_run, TEST_IMPORT_ERRORS, do_tag_discover, \
    combined_suites

unit_suite = do_tag_discover(tags_include='unittest',
                             tags_exclude='multiproc',
                               tests_exclude=TEST_IMPORT_ERRORS)
integration_suite = do_tag_discover(tags_include='integration',
                                      tags_exclude=('hdf5_settings', 'multiproc'),
                                      tests_exclude=TEST_IMPORT_ERRORS)
other_suite = do_tag_discover(tags_include='hdf5_settings')

suite_dict = {'1': unit_suite, '2': integration_suite, '3': other_suite}



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
        suite = combined_suites(unit_suite, integration_suite, other_suite)


    sys.argv=[sys.argv[0]]
    make_run(remove, folder, suite)