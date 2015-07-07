#!/bin/bash

echo "Installing Git and Sumatra Test"
# sudo apt-get install git
pip install GitPython
if [[ $TRAVIS_PYTHON_VERSION == 2* ]]
    then
        pip install django
        pip install Sumatra
    fi