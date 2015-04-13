#!/bin/bash

echo "Installing Git and Sumatra Test"
# sudo apt-get install git
travis_retry pip install GitPython==0.3.6 # Sumatra has a wrong version checking
# which thinks GitPython 1.0.0 is lower than 0.3.6 (only checking minor version :(
if [[ $TRAVIS_PYTHON_VERSION == 2* ]]
    then
        travis_retry pip install django==1.5
        travis_retry pip install Sumatra
    fi