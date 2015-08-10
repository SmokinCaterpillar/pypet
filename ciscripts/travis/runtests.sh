#!/bin/bash

set -e # To exit upon any error
set -u # Treat references to unset variables as an error

if [[ $TEST_SUITE == ON ]]
    then
        if [[ $TRAVIS_PYTHON_VERSION == 2.7* && $NEWEST == TRUE  ]]
            then
                # try with many files, i.e. do not remove data after every test
                # but only for one particular setting of the test matrix python = 2.7 and newest
                # packages
                echo "Running test suite and keeping all files"
                python ../../pypet/tests/all_tests.py -k
            else
                echo "Running test suite"
                python ../../pypet/tests/all_tests.py
            fi
    fi

if [[ $SCOOP == ON ]]
    then
        echo "Running SCOOP tests with SCOOP"
        python -m scoop ../../pypet/tests/scoop_run.py
        echo "SCOOP tests complete"
    fi

if [[ $GIT_TEST == ON ]]
    then

        mkdir git_sumatra_test
        cp ../../pypet/tests/integration/git_check.py git_sumatra_test
        cd git_sumatra_test
        echo "Initialise git repo"
        git init
        if [[ $TRAVIS_PYTHON_VERSION == 2* ]]
            then
                # Only use sumatra in case of Python 2
                echo "Initialise Sumatra Repo"
                smt init GitTest
            fi
        git config --global user.email "you@example.com"
        git config --global user.name "Your Name"
        echo "DummyDummyDummy">>dummy.txt # Create a new dummy file
        git add dummy.txt
        git add git_check.py
        git commit -m "First Commit"
        echo "Dummy2">>dummy.txt # Change the file
        echo "Running First Git Test"
        if [[ $COVERAGE == ON ]]
            then
                echo "Running git coverage"
                coverage run --parallel-mode --source=../../../pypet --omit=*/network.py,*/compat.py,*/ptcompat.py,*/pypet/tests/*,*/shareddata.py git_check.py
            else
                python git_check.py -f # Also test failing of git
            fi
        rm -rvf experiments
        echo "Running Second Git Test (without actual commit)"
        if [[ $COVERAGE == ON ]]
            then
                echo "Running git coverage"
                coverage run --parallel-mode --source=../../../pypet --omit=*/network.py,*/compat.py,*/ptcompat.py,*/pypet/tests/*,*/shareddata.py git_check.py
                mv -v .coverage* ../../../
            else
                python git_check.py -n # Test that git is not failing
            fi
        echo "Git Test complete, removing folder"
        cd ..
        rm -rvf git_sumatra_test
        echo "Removal complete"
    fi

if [[ $COVERAGE == ON ]]
    then
        cd ../../
        coverage run --parallel-mode --source=pypet --omit=*/network.py,*/compat.py,*/ptcompat.py,*/pypet/tests/*,*/shareddata.py ./pypet/tests/coverage_run.py
        coverage combine
        coveralls --verbose
        cd ciscripts/travis
    fi

if [[ $EXAMPLES == ON ]]
    then
        cd ../../pypet/tests
        python all_examples.py
        cd ../../ciscripts/travis
        if [[ $SCOOP == ON ]]
            then
                cd ../../examples
                echo "Running SCOOP example"
                python -m scoop example_21_scoop_multiprocessing.py
                echo "SCOOP example succesfull"
                cd ../ciscripts/travis
            fi
    fi
