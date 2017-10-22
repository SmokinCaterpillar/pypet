#!/bin/bash

set -e # To exit upon any error
set -u # Treat references to unset variables as an error

if [[ $TEST_SUITE == ON ]]
    then
        echo "Running test suite (with SCOOP)"
        python -m scoop -n 3 ../../pypet/tests/all_tests.py
    fi

if [[ $TEST_SUITE == MULTIPROC ]]
    then
        echo "Running test suite (with SCOOP)"
        python -m scoop -n 3 ../../pypet/tests/all_multi_core_tests.py
    fi

if [[ $TEST_SUITE == SINGLECORE ]]
    then
        echo "Running test suite (with SCOOP)"
        python -m scoop -n 3 ../../pypet/tests/all_single_core_tests.py
    fi

if [[ $GIT_TEST == ON ]]
    then

        mkdir git_sumatra_test
        cp ../../pypet/tests/integration/git_check.py git_sumatra_test
        cd git_sumatra_test
        echo "Initialise git repo"
        git init
        echo "Initialise Sumatra Repo"
        smt init GitTest
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
                coverage run --parallel-mode --source=../../../pypet --omit=*/compat.py,*/ptcompat.py,*/pypet/tests/*,*/shareddata.py git_check.py
            else
                python git_check.py -f # Also test failing of git
            fi
        rm -rvf experiments
        echo "Running Second Git Test (without actual commit)"
        if [[ $COVERAGE == ON ]]
            then
                echo "Running git coverage"
                coverage run --parallel-mode --source=../../../pypet --omit=*/compat.py,*/ptcompat.py,*/pypet/tests/*,*/shareddata.py git_check.py
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
        coverage run --parallel-mode --source=pypet --omit=*/compat.py,*/ptcompat.py,*/pypet/tests/*,*/shareddata.py ./pypet/tests/coverage_run.py
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
                python -m scoop -n 3 example_21_scoop_multiprocessing.py
                echo "SCOOP example succesfull"
                cd ../ciscripts/travis
            fi
    fi
