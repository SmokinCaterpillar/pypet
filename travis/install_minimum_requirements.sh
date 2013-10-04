#!/bin/bash

#Install Numpy and scipy
echo "+++++++++++++++++++ Installing NumPy 1.6.1 and Scipy 0.10.0 +++++++++++++++++++++"
pip install numpy==1.6.1
pip install scipy==0.10.0

#Install pandas
echo "++++++++++++++++++++ Installing pandas 0.12.0 ++++++++++++++++++++++++++++++++++++"
pip install pandas==0.12.0

#Install PyTables
echo "++++++++++++++++++++ Installing PyTables 2.3.1 ++++++++++++++++++++++++++++++++++++"
pip install tables==2.3.1

#Install Brian
echo "++++++++++++++++++++++ Installing Brian ++++++++++++++++++++++++++++++++++++++"
pip install brian

#Install GitPython
echo "+++++++++++++++++++++++++ Installing GitPython +++++++++++++++++++++++++++++++++"
pip install GitPython




exit 0
