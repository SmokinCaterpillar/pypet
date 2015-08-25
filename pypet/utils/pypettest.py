"""Short module to allow the running of tests via ``pypet.test()``"""

__author__ = 'Robert Meyer'


from pypet.tests.testutils.ioutils import TEST_IMPORT_ERROR, discover_tests, run_suite


def test(folder=None, remove=True, predicate=None):
    """Runs all pypet tests

    :param folder:

        Temporary folder to put data in, leave `None` for
        automatic choice.

    :param remove:

        If temporary data should be removed after the tests.

    :param predicate:

        Predicate to specify subset of tests. Must take three arguments
        ``class_name``, ``test_name``, ``tags`` and evaluate to `True` if
        a test should be run. Leave `None` for all tests.


    """
    if predicate is None:
        predicate = lambda class_name, test_name, tags: class_name != TEST_IMPORT_ERROR
    suite = discover_tests(predicate=predicate)
    run_suite(suite=suite, remove=remove, folder=folder)