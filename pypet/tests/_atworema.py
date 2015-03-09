__author__ = 'Robert Meyer'

from pypet.tests.testutils.ioutils import make_run, do_tag_discover, TEST_IMPORT_ERRORS

if __name__ == '__main__':
    suite = do_tag_discover(predicate= lambda class_name, test_name, tags:
                                                class_name != TEST_IMPORT_ERRORS)
    make_run(remove=False, folder=None, suite=suite)