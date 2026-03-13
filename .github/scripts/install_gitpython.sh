#!/bin/bash

echo "Installing Git and Sumatra Test"
pip install GitPython
pip install django
pip install pyyaml # otherwise smt init fails with yaml not defined error
pip install Sumatra
