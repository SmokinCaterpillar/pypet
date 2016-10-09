#!/bin/bash

echo "Installing Git and Sumatra Test"
# sudo apt-get install git
pip install GitPython
if [[ $TRAVIS_PYTHON_VERSION == 3* ]]
    then
        pip install django
        pip install pyyaml # otherwise smt init fails with yaml not defined error
        pip install Sumatra
    fi