from pypet.tests.testutils.ioutils import TEST_IMPORT_ERROR, discover_tests, run_suite

if __name__ == "__main__":
    suite = discover_tests(
        predicate=lambda class_name, test_name, tags: class_name != TEST_IMPORT_ERROR
    )
    run_suite(remove=False, folder=None, suite=suite)
