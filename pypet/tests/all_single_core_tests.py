__author__ = 'Robert Meyer'

import getopt
import sys

from pypet.tests.testutils.ioutils import make_run, TEST_IMPORT_ERRORS, do_tag_discover, \
    combined_suites

unit_pred = lambda class_name, test_name, tags: ('unittest' in tags and
                                                 'multiproc' not in tags)
unit_suite = do_tag_discover(unit_pred)

exclude_set = set(('hdf5_settings', 'multiproc', 'merge'))
integration_pred = lambda class_name, test_name, tags: ('integration' in tags and
                                                         not bool(exclude_set & tags))
integration_suite = do_tag_discover(integration_pred)

include_set = set(('hdf5_settings', 'links', 'merge'))
integration_pred_2 = lambda class_name, test_name, tags: ('integration' in tags and
                                                          bool(include_set & tags) and
                                                          'multiproc' not in tags and
                                                          'links' not in tags)
integration_suite_2 = do_tag_discover(integration_pred_2)

suite_dict = {'1': unit_suite, '2': integration_suite, '3': integration_suite_2}



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
        suite = combined_suites(unit_suite, integration_suite, integration_suite_2)


    sys.argv=[sys.argv[0]]
    make_run(remove, folder, suite)