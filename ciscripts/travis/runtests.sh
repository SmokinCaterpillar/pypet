#!/bin/bash

set -e # To exit upon any error
set -u # Treat references to unset variables as an error

if [[ $EXAMPLES == ON ]]
    then
        conda install matplotlib
        cd ../../pypet/tests
        python all_examples.py
        cd ../../ciscripts/travis
    fi

if [[ $GIT_TEST == ON ]]
    then
        echo "Installing Git and Sumatra Test"
        # sudo apt-get install git
        pip install --pre GitPython
        pip install django==1.5
        pip install Sumatra
        mkdir git_sumatra_test
        cp ../../pypet/tests/integrationtests/git_check.py git_sumatra_test
        cd git_sumatra_test
        git init
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
                coverage run --parallel-mode --source=../../../pypet --omit=*/network.py,*/compat.py,*/ptcompat.py,*/pypet/tests/*,*/shareddata.py git_check.py
            else
                python git_check.py
            fi
        rm -rvf experiments
        echo "Running Second Git Test (without actual commit)"
        if [[ $COVERAGE == ON ]]
            then
                echo "Running git coverage"
                coverage run --parallel-mode --source=../../../pypet --omit=*/network.py,*/compat.py,*/ptcompat.py,*/pypet/tests/*,*/shareddata.py git_check.py
                mv -v .coverage* ../../../
            else
                python git_check.py
            fi
        echo "Git Test complete, removing folder"
        cd ..
        rm -rvf git_sumatra_test
        echo "Removal complete"
    fi

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

if [[ $COVERAGE == ON ]]
    then
        cd ../../
        coverage run --parallel-mode --source=pypet --omit=*/network.py,*/compat.py,*/ptcompat.py,*/pypet/tests/*,*/shareddata.py ./pypet/tests/run_coverage.py
        coverage combine
        coveralls --verbose
        cd ciscripts/travis
    fi
