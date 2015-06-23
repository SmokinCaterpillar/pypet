#!/bin/bash

echo "Installing Git and Sumatra Test"
# sudo apt-get install git
pip install GitPython==0.3.6 # Sumatra has a wrong version checking
# which thinks GitPython 1.0.0 is lower than 0.3.6 (only checking minor version :(
if [[ $TRAVIS_PYTHON_VERSION == 2* ]]
    then
        pip install django==1.6 #maybe this works now with newer django versions
        pip install Sumatra
#        git clone https://github.com/open-research/sumatra.git
#        cd sumatra
#        python setup.py install
#        cd ..
    fi