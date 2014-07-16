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
                sudo apt-get install libcurl4-gnutls-dev libexpat1-dev gettext libz-dev libssl-dev
                sudo apt-get install git
                pip install --pre GitPython
                pip install Sumatra
                mkdir git_sumatra_test
                cp pypet/tests/test_git.py git_sumatra_test
                cd git_sumatra_test
                git init
                smt init GitTest
                echo "Running Git Test"
                python test_git.py
                cd ..
                rm -rvf git_sumatra_test

            else
                python ./pypet/tests/all_tests.py
            fi
    fi