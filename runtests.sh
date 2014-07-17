#!/bin/bash

set -e # To exit upon any error
set -u # Treat references to unset variables as an error

if [[ $COVERAGE == ON ]]
    then
        coverage run --parallel-mode --timid --source=pypet --omit=pypet/brian/*,pypet/tests/* -m pypet.tests.all_single_core_tests
        coverage combine
    else
        if [[ $GIT_TEST == ON ]]
            then
                echo "Installing Git and Sumatra Test"
                # sudo apt-get install libcurl4-gnutls-dev libexpat1-dev gettext libz-dev libssl-dev
                sudo apt-get install git
                pip install --pre GitPython
                pip install Sumatra
                mkdir git_sumatra_test
                cp pypet/tests/test_git.py git_sumatra_test
                cd git_sumatra_test
                git init
                smt init GitTest
                git config --global user.email "you@example.com"
                git config --global user.name "Your Name"
                echo "DummyDummyDummy">>dummy.txt
                git add dummy.txt
                git commit -m "First Commit"
                git add git_test.py
                echo "Running First Git Test"
                python test_git.py
                rm -rvf experiments
                echo "Running Second Git Test (without actual commit)"
                python test_git.py
                echo "Git Test complete, removing folder"
                cd ..
                rm -rvf git_sumatra_test
                echo "Removal complete"

            else
                python ./pypet/tests/all_tests.py
            fi
    fi