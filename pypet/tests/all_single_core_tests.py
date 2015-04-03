__author__ = 'Robert Meyer'


from pypet.tests.testutils.ioutils import run_suite, TEST_IMPORT_ERROR, discover_tests, \
    parse_args

unit_pred = lambda class_name, test_name, tags: ('unittest' in tags and
                                                 'multiproc' not in tags)
unit_suite = discover_tests(unit_pred)

exclude_set = set(('hdf5_settings', 'multiproc', 'merge'))
integration_pred = lambda class_name, test_name, tags: ('integration' in tags and
                                                         not bool(exclude_set & tags))
integration_suite = discover_tests(integration_pred)

include_set = set(('hdf5_settings', 'links', 'merge'))
integration_pred_2 = lambda class_name, test_name, tags: ('integration' in tags and
                                                          bool(include_set & tags) and
                                                          'multiproc' not in tags and
                                                          'links' not in tags)
integration_suite_2 = discover_tests(integration_pred_2)

suite_dict = {'1': unit_suite, '2': integration_suite, '3': integration_suite_2}


if __name__ == '__main__':
    opt_dict = parse_args()
    suite = None
    if 'suite_no' in opt_dict:
        suite_no = opt_dict.pop('suite_no')
        suite = suite_dict[suite_no]

    if suite is None:
        pred = lambda class_name, test_name, tags: ('multiproc' not in tags and
                                                        class_name != TEST_IMPORT_ERROR)
        suite = discover_tests(pred)

    run_suite(suite=suite, **opt_dict)
