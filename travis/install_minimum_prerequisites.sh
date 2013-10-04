#Install requirements for scipy
sudo apt-get install gfortran libopenblas-dev liblapack-dev


#Requirements for PyTables
echo "+++++++++++++++++++++++++ Installing NumExpr 2.0.0 +++++++++++++++++++++++"
pip install numexpr==1.4.1
echo "+++++++++++++++++++++++++ Installing cython 0.13.0 ++++++++++++++++++++++++"
pip install cython ==0.13.0


exit 0