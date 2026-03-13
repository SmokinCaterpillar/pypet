try:
    import pypet  # noqa: F401
except ImportError:
    import sys

    sys.path.append("/media/data/PYTHON_WORKSPACE/pypet-project")


from pypet.tests.integration.environment_scoop_test import scoop_not_functional_check
from pypet.tests.testutils.ioutils import discover_tests, parse_args, run_suite

scoop_suite = discover_tests(lambda class_name, test_name, tags: "scoop" in tags)


if __name__ == "__main__":
    if scoop_not_functional_check():
        raise RuntimeError("Not running in SCOOP mode!")
    opt_dict = parse_args()
    run_suite(suite=scoop_suite, **opt_dict)
